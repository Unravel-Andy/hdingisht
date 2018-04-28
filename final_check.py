#!/usr/bin/env python
#v1.1.0
from subprocess import call, check_output
import json,argparse, re, base64
from time import sleep
import hdinsight_common.Constants as Constants
import hdinsight_common.ClusterManifestParser as ClusterManifestParser

parser = argparse.ArgumentParser()
parser.add_argument('-host','--unravel-host', help='Unravel Server hostname', dest='unravel', required=True)
parser.add_argument('-user','--username', help='Ambari login username')
parser.add_argument('-pass','--password', help='Ambari login password')
parser.add_argument('-c','--cluster_name', help='ambari cluster name')
parser.add_argument('-s','--spark_ver', help='spark version')
parser.add_argument('-hive','--hive_ver', help='hive version', required=True)
parser.add_argument('-l','--am_host', help='ambari host', required=True)
argv = parser.parse_args()
argv.username = Constants.AMBARI_WATCHDOG_USERNAME
base64pwd = ClusterManifestParser.parse_local_manifest().ambari_users.usersmap[Constants.AMBARI_WATCHDOG_USERNAME].password
argv.password = base64.b64decode(base64pwd)
argv.cluster_name = ClusterManifestParser.parse_local_manifest().deployment.cluster_name
unrave_server = argv.unravel
argv.unravel = argv.unravel.split(':')[0]
argv.spark_ver = argv.spark_ver.split('.')
argv.hive_ver = argv.hive_ver.split('.')
log_dir='/tmp/unravel/'
spark_def_json = log_dir + 'spark-def.json'
hive_env_json = log_dir + 'hive-env.json'
hadoop_env_json = log_dir + 'hadoop-env.json'
mapred_site_json = log_dir + 'mapred-site.json'
hive_site_json = log_dir + 'hive-site.json'
tez_site_json = log_dir + 'tez-site.json'

def am_req(api_name=None, full_api=None):
    if api_name:
        result = json.loads(check_output('curl -u {0}:\'{1}\' -s -H \'X-RequestedBy:ambari\' -X GET http://{2}:8080/api/v1/clusters/{3}/{4}'.format(argv.username, argv.password, argv.am_host, argv.cluster_name, api_name), shell=True))
    elif full_api:
        result = json.loads(check_output('curl -u {0}:\'{1}\' -s -H \'X-RequestedBy:ambari\' -X GET {2}'.format(argv.username, argv.password,full_api), shell=True))
    return result

#####################################################################
#    Check current configuration and update if not correct          #
#           Give None value if need to skip configuration           #
#####################################################################
def check_configs(hdfs_url=None,hive_env_content=None,hadoop_env_content=None,hive_site_configs=None,spark_defaults_configs=None,mapred_site_configs=None,tez_site_configs=None):
    print('HDFS_URL: ')
    print(hdfs_url)
    print('Hive-env: ')
    print(hive_env_content)
    print('Hadoop-env: ')
    print(hadoop_env_content)
    print('hive-site: ')
    print(hive_site_configs)
    print('spark-defaults: ')
    print(spark_defaults_configs)
    print('mapred-site: ')
    print(mapred_site_configs)

    # spark-default
    if spark_defaults_configs:
        try:
            spark_def_ver = get_spark_defaults()
            if not spark_def_ver:
            spark_def = read_json(spark_def_json)

            if all(x in spark_def for _,x in spark_defaults_configs.iteritems()):
                print(get_spark_defaults() + '\n\nSpark Config is correct\n')
            else:
                print('\n\nSpark Config is not correct\n')
                new_spark_def = json.loads(spark_def)
                for key,val in spark_defaults_configs.iteritems():
                    try:
                        print (key+': ',new_spark_def['properties'][key])
                        if (key == 'spark.driver.extraJavaOptions' or key == 'spark.executor.extraJavaOptions') and val not in spark_def:
                            new_spark_def['properties'][key] += ' ' + val
                        elif key != 'spark.driver.extraJavaOptions' and key != 'spark.executor.extraJavaOptions':
                            new_spark_def['properties'][key] = val
                    except:
                        print (key+': ', 'None')
                        new_spark_def['properties'][key] = val
                write_json(spark_def_json, json.dumps(new_spark_def))
                update_config(spark_def_ver, set_file=spark_def_json)
            sleep(5)
        except:
            pass

    # hive-env
    if hive_env_content:
        get_config('hive-env', set_file=hive_env_json)
        hive_env = read_json(hive_env_json)
        if hive_env_content.split(' ')[1] in hive_env:
            print('\nAUX_CLASSPATH is in hive\n')
        else:
            print('\n\nAUX_CLASSPATH is missing\n')
            hive_env = json.loads(hive_env)
            content = hive_env['properties']['content']
            #content = hive_env[hive_env.find('\"content\": \"')+12:re.search('{% endif %}(\s*?\n*?.*?){0,}",', hive_env).span()[1]-2]
            print('hive-env content: ', content)
            hive_env['properties']['content'] = content + '\n' + hive_env_content
            sleep(2)
            write_json(hive_env_json, json.dumps(hive_env))
            update_config('hive-env', set_file=hive_env_json)
            sleep(5)

    # hive-site
    if hive_site_configs:
        get_config('hive-site', set_file=hive_site_json)
        hive_site = read_json(hive_site_json)

        try:
            check_hive_site = all(x in hive_site for _,x in hive_site_configs.iteritems())
        except Exception as e:
            print(e)
            check_hive_site = False
        if check_hive_site:
            print('\nCustom hive-site configs are correct\n')
        else:
            print('\n\nCustom hive-site configs are missing\n')
            hive_site = json.loads(hive_site)
            for key,val in hive_site_configs.iteritems():
                try:
                    print(key+': ', hive_site['properties'][key])
                    if re.match('hive.exec.(pre|post|failure).hooks', key) and val not in hive_site['properties'][key]:
                        hive_site['properties'][key] += ',' + val
                    else:
                        hive_site['properties'][key] = val
                except:
                    print (key+': ', 'None')
                    hive_site['properties'][key] = val

            write_json(hive_site_json, json.dumps(hive_site))
            update_config('hive-site', set_file=hive_site_json)
        sleep(5)

    # hadoop-env
    if hadoop_env_content:
        get_config('hadoop-env', set_file=hadoop_env_json)
        hadoop_env = read_json(hadoop_env_json)

        if hadoop_env.find(hadoop_env_content.split(' ')[1]) > -1:
            print('\nHADOOP_CLASSPATH is correct\n')
        else:
            hadoop_env = json.loads(hadoop_env)
            print('\nHADOOP_CLASSPATH is missing, updating\n')

            content = hadoop_env['properties']['content']

            print('Haddop-env content: ', content)
            hadoop_env['properties']['content'] = content + '\n' + hadoop_env_content
            sleep(2)
            write_json(hadoop_env_json, json.dumps(hadoop_env))
            update_config('hadoop-env', set_file=hadoop_env_json)
        sleep(5)

    # mapred-site
    if mapred_site_configs:
        get_config('mapred-site', set_file=mapred_site_json)
        mapred_site = json.loads(read_json(mapred_site_json))

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
                    if val not in mapred_site['properties'][key]:
                        mapred_site['properties'][key] += ' ' + val
                except:
                    print (key+': ', 'None')
                    mapred_site['properties'][key] = val
            write_json(mapred_site_json, json.dumps(mapred_site))
            update_config('mapred-site', set_file=mapred_site_json)
        sleep(5)

    #tez-site
    if tez_site_configs:
        get_config('tez-site', set_file=tez_site_json)
        tez_site = json.loads(read_json(tez_site_json))
        make_change = False
        for key,val in tez_site_configs.iteritems():
            if val in tez_site['properties'][key]:
                print(key + 'is correct')
            else:
                print(key + 'is not correct')
                tez_site['properties'][key] += ' ' + val
                make_change = True
        if make_change:
            write_json(tez_site_json, json.dumps(tez_site))
            update_config('tez-site', set_file=tez_site_json)

def get_latest_req_stat():
    cluster_requests = am_req(api_name='requests')
    latest_cluster_req = cluster_requests['items'][-1]['href']
    return (am_req(full_api=latest_cluster_req)['Requests']['request_status'])

def get_config(config_name, set_file=None):
    if set_file:
        return check_output('python /tmp/unravel/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c {4} -f {5}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, config_name, set_file), shell=True)
    else:
        return check_output('python /tmp/unravel/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c {4}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, config_name), shell=True)

def get_spark_defaults():
    try:
        spark_defaults =check_output('python /tmp/unravel/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c spark-defaults -f {4}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, spark_def_json), shell=True)
        return ('spark-defaults')
    except:
        try:
            spark_defaults = check_output('python /tmp/unravel/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c spark2-defaults -f {4}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, spark_def_json), shell=True)
            return ('spark2-defaults')
        except:
            return('None')

#####################################################################
#   Read the JSON file and return the plain text                    #
#####################################################################
def read_json(json_file_location):
    with open(json_file_location,'r') as f:
        result = f.read()
        f.close()
    return result

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

def write_json(json_file_location, content_write):
    with open(json_file_location,'w') as f:
        f.write(content_write)
        f.close()

core_site = get_config('core-site')
hdfs_url = json.loads(core_site[core_site.find('{'):])['properties']['fs.defaultFS']
hive_env_content = 'export AUX_CLASSPATH=${AUX_CLASSPATH}:/usr/local/unravel_client/unravel-hive-%s.%s.0-hook.jar' % (argv.hive_ver[0],argv.hive_ver[1])
hadoop_env_content = 'export HADOOP_CLASSPATH=${HADOOP_CLASSPATH}:/usr/local/unravel_client/unravel-hive-%s.%s.0-hook.jar' % (argv.hive_ver[0],argv.hive_ver[1])
hive_site_configs = {'hive.exec.driver.run.hooks': 'com.unraveldata.dataflow.hive.hook.HiveDriverHook',
                    'com.unraveldata.hive.hdfs.dir': '/user/unravel/HOOK_RESULT_DIR',
                    'com.unraveldata.hive.hook.tcp': 'true',
                    'com.unraveldata.host':argv.unravel,
                    'hive.exec.pre.hooks': 'com.unraveldata.dataflow.hive.hook.HivePreHook',
                    'hive.exec.post.hooks': 'com.unraveldata.dataflow.hive.hook.HivePostHook',
                    'hive.exec.failure.hooks': 'com.unraveldata.dataflow.hive.hook.HiveFailHook'
                    }
spark_defaults_configs={'spark.eventLog.dir':hdfs_url + '/var/log/spark/apps',
                        'spark.history.fs.logDirectory':hdfs_url + '/var/log/spark/apps',
                        'spark.unravel.server.hostport':argv.unravel+':4043',
                        'spark.driver.extraJavaOptions':'-Dcom.unraveldata.client.rest.shutdown.ms=300 -javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=libs=spark-%s.%s,config=driver' % (argv.spark_ver[0],argv.spark_ver[1]),
                        'spark.executor.extraJavaOptions':'-Dcom.unraveldata.client.rest.shutdown.ms=300 -javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=libs=spark-%s.%s,config=executor' % (argv.spark_ver[0],argv.spark_ver[1])}
mapred_site_configs = {'yarn.app.mapreduce.am.command-opts':'-javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=libs=mr -Dunravel.server.hostport=%s:4043' % argv.unravel,
                        'mapreduce.task.profile':'true',
                        'mapreduce.task.profile.maps':'0-5',
                        'mapreduce.task.profile.reduces':'0-5',
                        'mapreduce.task.profile.params':'-javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=libs=mr -Dunravel.server.hostport=%s:4043' % argv.unravel}
tez_site_configs = {
                    'tez.am.launch.cmd-opts':'-javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=libs=mr,config=tez -Dunravel.server.hostport=%s:4043' % argv.unravel,
                    'tez.task.launch.cmd-opts':'-javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=libs=mr,config=tez -Dunravel.server.hostport=%s:4043' % argv.unravel
                    }

def main():
    sleep(30)
    # print('Checking Ambari Operations')
    # while(get_latest_req_stat() not in ['COMPLETED','FAILED','ABORTED']):
    #     print('Operations Status:' + get_latest_req_stat())
    #     sleep(60)
    # print('All Operations are completed, Comparing configs')

    check_configs(
                  hdfs_url=hdfs_url,
                  hive_env_content=hive_env_content,
                  hadoop_env_content=hadoop_env_content,
                  hive_site_configs=hive_site_configs,
                  spark_defaults_configs=spark_defaults_configs,
                  mapred_site_configs=mapred_site_configs,
                 )

    restart_services()

if __name__ == '__main__':
    main()
