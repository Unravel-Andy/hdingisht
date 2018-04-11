from time import sleep
from subprocess import call, check_output
import base64, json, argparse, re, os, urllib, sys
import hdinsight_common.Constants as Constants
import hdinsight_common.ClusterManifestParser as ClusterManifestParser

parser = argparse.ArgumentParser()
parser.add_argument('-host','--unravel-host', help='Unravel Server hostname', dest='unravel')
parser.add_argument('-user','--username', help='Ambari login username')
parser.add_argument('-pass','--password', help='Ambari login password')
parser.add_argument('-c','--cluster_name', help='ambari cluster name')
parser.add_argument('-s','--spark_ver', help='spark version')
parser.add_argument('-hive','--hive_ver', help='hive version')
parser.add_argument('-l','--am_host', help='ambari host', default='headnodehost')
argv = parser.parse_args()

if not argv.unravel:
    argv.unravel = check_output(['hostname', '-i']).strip()
if not argv.username:
    argv.username = Constants.AMBARI_WATCHDOG_USERNAME
if not argv.password:
    base64pwd = ClusterManifestParser.parse_local_manifest().ambari_users.usersmap[Constants.AMBARI_WATCHDOG_USERNAME].password
    argv.password = base64.b64decode(base64pwd)
if not argv.cluster_name:
    argv.cluster_name = ClusterManifestParser.parse_local_manifest().deployment.cluster_name
if not argv.spark_ver:
    try:
        argv.spark_ver = check_output('$(which spark-submit) --version 2>&1 | grep -oP \'.*?version\s+\K([0-9.]+)\'',shell=True).split('\n')[0].split('.')
    except:
        argv.spark_ver = '2.1.0'
if not argv.hive_ver:
    argv.hive_ver = check_output('$(which hive) --version 2>/dev/null | grep -Po \'Hive \K([0-9]+\.[0-9]+\.[0-9]+)\'',shell=True).strip()
    argv.hive_ver = argv.hive_ver.split('.')
hosts_list = check_output('curl -s -u %s:\'%s\' -G "http://%s:8080/api/v1/clusters/%s/hosts" |grep "host_name" |awk \'{ print $3}\' |tr -d \'"\' |grep -vi zk'
                        % (argv.username, argv.password, 'headnodehost', argv.cluster_name),shell=True).strip().split('\n')
script_location = 'https://raw.githubusercontent.com/Unravel-Andy/hdingisht/test/on-premises/hdi_premises_sensor_deploy_.sh'

log_dir='/tmp/unravel/'
spark_def_json = log_dir + 'spark-def.json'
hive_env_json = log_dir + 'hive-env.json'
hive_site_json = log_dir + 'hive-site.json'
hadoop_env_json = log_dir + 'hadoop-env.json'
mapred_site_json = log_dir + 'mapred-site.json'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
if not os.path.exists(log_dir + 'configs.py'):
    print('Downloading configs.py')
    urllib.urlretrieve("https://raw.githubusercontent.com/Unravel-Andy/hdingisht/master/configs.py", log_dir + "configs.py")
sys.stderr = open(log_dir + 'hdi_onpremises_setup.err','w')

#####################################################################
# Ambari Get API functions                                          #
#####################################################################
def am_req(api_name=None, full_api=None):
    if api_name:
        result = json.loads(check_output('curl -u {0}:\'{1}\' -s -H \'X-RequestedBy:ambari\' -X GET http://{2}:8080/api/v1/clusters/{3}/{4}'.format(argv.username, argv.password, argv.am_host, argv.cluster_name, api_name), shell=True))
    elif full_api:
        result = json.loads(check_output('curl -u {0}:\'{1}\' -s -H \'X-RequestedBy:ambari\' -X GET {2}'.format(argv.username, argv.password,full_api), shell=True))
    return result

#####################################################################
# Check current configuration and update if not correct             #
#####################################################################
def check_configs(hdfs_url=None,hive_env_content=None,hadoop_env_content=None,hive_site_configs=None,spark_defaults_configs=None,mapred_site_configs=None):
    print('HDFS_URL: ' + hdfs_url)
    print('Hive-env: ' + hive_env_content)
    print('Hadoop-env: ' + hadoop_env_content)
    print('hive-site: ' + str(hive_site_configs))
    print('spark-defaults: ' + str(spark_defaults_configs))
    print('mapred-site: ' + str(mapred_site_configs))

    # spark-default
    if spark_defaults_configs:
        spark_def_ver = get_spark_defaults()
        with open(spark_def_json, 'r') as f:
            spark_def = f.read()
            f.close()
        if all(x in spark_def for _,x in spark_defaults_configs.iteritems()):
            print(get_spark_defaults() + '\n\nSpark Config is correct\n')
        else:
            print('\n\nSpark Config is not correct\n')
            new_spark_def = json.loads('{' + spark_def + '}')
            for key,val in spark_defaults_configs.iteritems():
                try:
                    print (key+': ',new_spark_def['properties'][key])
                except:
                    print (key+': ', 'None')
                if (key == 'spark.driver.extraJavaOptions' or key == 'spark.executor.extraJavaOptions') and val not in spark_def:
                    new_spark_def['properties'][key] += ' ' + val
                elif key != 'spark.driver.extraJavaOptions' and key != 'spark.executor.extraJavaOptions':
                    new_spark_def['properties'][key] = val
            with open(spark_def_json, 'w') as f:
                f.write(json.dumps(new_spark_def)[1:-1])
                f.close()
            update_config(spark_def_ver, set_file=spark_def_json)
        sleep(5)

    # hive-env
    if hive_env_content:
        get_config('hive-env', set_file=hive_env_json)
        with open(hive_env_json,'r') as f:
            hive_env = f.read()
            f.close()
        if hive_env_content.split(' ')[1] in hive_env:
            print('\nAUX_CLASSPATH is in hive\n')
        else:
            print('\n\nAUX_CLASSPATH is missing\n')
            content = hive_env[hive_env.find('\"content\": \"')+12:hive_env.find('{% endif %}\"')+11]
            print('hive-env content: ', content)
            new_content = json.dumps(content + '\n' + hive_env_content)[1:-1]
            sleep(2)
            with open(hive_env_json,'w') as f:
                f.write(hive_env.replace(content, new_content, 1))
                f.close()
            update_config('hive-env', set_file=hive_env_json)
            sleep(5)

    # hive-site
    if hive_site_configs:
        get_config('hive-site', set_file=hive_site_json)
        with open(hive_site_json,'r') as f:
            hive_site = f.read()
            f.close()
        try:
            check_hive_site = all(x in hive_site for _,x in hive_site_configs.iteritems())
        except Exception as e:
            print(e)
            check_hive_site = False
        if check_hive_site:
            print('\nCustom hive-site configs are correct\n')
        else:
            print('\n\nCustom hive-site configs are missing\n')
            hive_site = json.loads('{' + hive_site + '}')
            for key,val in hive_site_configs.iteritems():
                try:
                    print(key+': ', hive_site['properties'][key])
                except:
                    print (key+': ', 'None')
                if re.match('hive.exec.(pre|post|failure).hooks', key) and val not in hive_site['properties'][key]:
                    hive_site['properties'][key] += ',' + val
                else:
                    hive_site['properties'][key] = val

        sleep(5)

    # hadoop-env
    if hadoop_env_content:
        get_config('hadoop-env', set_file=hadoop_env_json)
        with open(hadoop_env_json,'r') as f:
            hadoop_env = f.read()
            f.close()
        if hadoop_env.find(hadoop_env_content.split(' ')[1]) > -1:
            print('\nHADOOP_CLASSPATH is correct\n')
        else:
            print('\nHADOOP_CLASSPATH is missing, updating\n')
            content = hadoop_env[hadoop_env.find('\"content\": \"')+12:hadoop_env.find('hdfs_user_nofile_limit')-6]
            print('Haddop-env content: ', content)
            new_content = json.dumps(content + '\n' + hadoop_env_content)[1:-1]
            sleep(2)
            with open(hadoop_env_json,'w') as f:
                f.write(hadoop_env.replace(content, new_content, 1))
                f.close()
            # update_config('hadoop-env', set_file=hadoop_env_json)
            sleep(5)

    # mapred-site
    if mapred_site_configs:
        get_config('mapred-site',set_file=mapred_site_json)
        with open(mapred_site_json,'r') as f:
            mapred_site = json.loads('{' + f.read() + '}')
            f.close()

        try:
            check_mapr_site = all(val in mapred_site['properties'][key] for key, val in mapred_site_configs.iteritems())
        except Exception as e:
            print(e)
            check_mapr_site = False
        if check_mapr_site:
            print('\nmapred-site correct')
        else:
            print('\n\nmapr-site missing')
            for key,val in mapred_site_configs.iteritems():
                try:
                    print(key+': ',mapred_site['properties'][key])
                except:
                    print (key+': ', 'None')
                if key == 'yarn.app.mapreduce.am.command-opts' and val not in mapred_site['properties'][key]:
                    mapred_site['properties'][key] += ' ' + val
                else:
                    mapred_site['properties'][key] = val

            with open(mapred_site_json,'w') as f:
                f.write(json.dumps(mapred_site)[1:-1])
                f.close()
            update_config('mapred-site', set_file=mapred_site_json)

def check_running_ops():
    print('\nChecking Ambari Operations\n')
    while(get_latest_req_stat() not in ['COMPLETED','FAILED']):
        print('Operations Status:' + get_latest_req_stat())
        sleep(30)
    print('\nAll Operations are completed, Comparing configs\n')

def deploy_sensor():
    call("""curl -u {0}:'{1}' -i -H 'X-Requested-By: ambari' -X POST -d \
    '{{"RequestInfo": {{"action":"run_customscriptaction", "context" :"Unrvel: Custom Script Action","operation_level":"host_component", \
    "parameters":{{"script_location":"{2}",\
    "script_params":"","storage_account":"","storage_key":"","storage_container":"","blob_name":""}}}},\
    "Requests/resource_filters":[{{"hosts":"{3}"\
    }}]}}' http://headnodehost:8080/api/v1/clusters/{4}/requests\
    """.format(argv.username, argv.password, script_location, str(','.join(hosts_list)), argv.cluster_name),shell=True)

#########################################################################
#   Get current configuration                                           #
#   --config_name configuration name e.g hive-env, spark-defaults       #
#   --set_file  path to the file that the configuration will be saved   #
#########################################################################
def get_config(config_name, set_file=None):
    if set_file:
        return check_output('python /tmp/unravel/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c {4} -f {5}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, config_name, set_file), shell=True)
    else:
        return check_output('python /tmp/unravel/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c {4}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, config_name), shell=True)

#####################################################################
# Get Ambari Last Operations                                        #
#####################################################################
def get_latest_req_stat():
    cluster_requests = am_req(api_name='requests')
    latest_cluster_req = cluster_requests['items'][-1]['href']
    return (am_req(full_api=latest_cluster_req)['Requests']['request_status'])

#####################################################################
#   Determine whether spark or spark2 is installed in cluster       #
#####################################################################
def get_spark_defaults():
    try:
        spark_defaults =check_output('python /tmp/unravel/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c spark-defaults -f {4}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, spark_def_json), shell=True)
        return ('spark-defaults')
    except:
        spark_defaults = check_output('python /tmp/unravel/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c spark2-defaults -f {4}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, spark_def_json), shell=True)
        return ('spark2-defaults')

#####################################################################
#   Restart All Required Services                                   #
#####################################################################
def restart_services():
    call('curl -u {0}:\'{1}\' -i -H \'X-Requested-By: ambari\' -X POST -d \'{{\"RequestInfo\": {{\"command\":\"RESTART\",\"context\" :\"Unravel request: Restart Services\",\"operation_level\":\"host_component\"}},\"Requests/resource_filters\":[{{\"hosts_predicate\":\"HostRoles/stale_configs=true\"}}]}}\' http://{2}:8080/api/v1/clusters/{3}/requests > /tmp/Restart.out 2> /tmp/Restart.err < /dev/null &'.format(argv.username, argv.password, argv.am_host, argv.cluster_name),shell=True)

def update_config(config_name,config_key=None,config_value=None, set_file=None):
    try:
        if set_file:
            return check_output('python /tmp/unravel/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a set -c {4} -f {5}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, config_name, set_file), shell=True)
        else:
            return check_output('python /tmp/unravel/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a set -c {4} -k {5} -v {6}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, config_name, config_key, config_value), shell=True)
    except:
        print('\Update %s configuration failed' % config_name)
        
def main():
    core_site = get_config('core-site')
    hdfs_url = json.loads(core_site[core_site.find('properties\":')+13:])['fs.defaultFS']
    hive_env_content = 'export AUX_CLASSPATH=${AUX_CLASSPATH}:/usr/local/unravel_client/unravel-hive-%s.%s.0-hook.jar' % (argv.hive_ver[0],argv.hive_ver[1])
    hadoop_env_content = 'export HADOOP_CLASSPATH=${HADOOP_CLASSPATH}:/usr/local/unravel_client/unravel-hive-%s.%s.0-hook.jar' % (argv.hive_ver[0],argv.hive_ver[1])
    hive_site_configs = {
                        'hive.exec.driver.run.hooks': 'com.unraveldata.dataflow.hive.hook.HiveDriverHook',
                        'com.unraveldata.hive.hdfs.dir': '/user/unravel/HOOK_RESULT_DIR',
                        'com.unraveldata.hive.hook.tcp': 'true',
                        'com.unraveldata.host':argv.unravel,
                        'hive.exec.pre.hooks': 'com.unraveldata.dataflow.hive.hook.HivePreHook',
                        'hive.exec.post.hooks': 'com.unraveldata.dataflow.hive.hook.HivePostHook',
                        'hive.exec.failure.hooks': 'com.unraveldata.dataflow.hive.hook.HiveFailHook'
                        }
    spark_defaults_configs={
                            #'spark.eventLog.dir':hdfs_url + '/var/log/spark/apps',
                            #'spark.history.fs.logDirectory':hdfs_url + '/var/log/spark/apps',
                            'spark.unravel.server.hostport':argv.unravel+':4043',
                            'spark.driver.extraJavaOptions':'-Dcom.unraveldata.client.rest.shutdown.ms=300 -javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=libs=spark-%s.%s,config=driver' % (argv.spark_ver[0],argv.spark_ver[1]),
                            'spark.executor.extraJavaOptions':'-Dcom.unraveldata.client.rest.shutdown.ms=300 -javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=libs=spark-%s.%s,config=executor' % (argv.spark_ver[0],argv.spark_ver[1])
                            }
    mapred_site_configs = {
                            'yarn.app.mapreduce.am.command-opts':'-javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=libs=mr -Dunravel.server.hostport=%s:4043' % argv.unravel,
                            'mapreduce.task.profile':'true',
                            'mapreduce.task.profile.maps':'0-5',
                            'mapreduce.task.profile.reduces':'0-5',
                            'mapreduce.task.profile.params':'-javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=libs=mr -Dunravel.server.hostport=%s:4043' % argv.unravel
                            }

    deploy_sensor()

    check_running_ops()

    check_configs(hdfs_url=hdfs_url, hive_env_content=hive_env_content, hadoop_env_content=hadoop_env_content, hive_site_configs=hive_site_configs, spark_defaults_configs=spark_defaults_configs, mapred_site_configs=mapred_site_configs)

    restart_services()

if __name__ == '__main__':
    main()
