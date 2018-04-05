from subprocess import call, check_output
import urllib2,base64,json,argparse, re
from time import sleep

parser = argparse.ArgumentParser()
parser.add_argument('-host','--unravel-host', help='Unravel Server hostname', dest='unravel', required=True)
parser.add_argument('-user','--username', help='ambari username', required=True)
parser.add_argument('-pass','--password', help='ambari password', required=True)
parser.add_argument('-c','--cluster_name', help='ambari cluster name', required=True)
parser.add_argument('-s','--spark_ver', help='spark version', required=True)
parser.add_argument('-l','--am_host', help='ambari host', required=True)
argv = parser.parse_args()
unrave_server = argv.unravel
argv.unravel = argv.unravel.split(':')[0]
argv.spark_ver = argv.spark_ver.split('.')
log_dir='/tmp/unravel/'
spark_def_json = log_dir + 'spark-def.json'
hive_env_json = log_dir + 'hive-env.json'
hadoop_env_json = log_dir + 'hadoop-env.json'
mapred_site_json = log_dir + 'mapred-site.json'

def am_req(api_name=None, full_api=None):
    if api_name:
        result = json.loads(check_output('curl -u {0}:\'{1}\' -s -H \'X-RequestedBy:ambari\' -X GET http://{2}:8080/api/v1/clusters/{3}/{4}'.format(argv.username, argv.password, argv.am_host, argv.cluster_name, api_name), shell=True))
    elif full_api:
        result = json.loads(check_output('curl -u {0}:\'{1}\' -s -H \'X-RequestedBy:ambari\' -X GET {2}'.format(argv.username, argv.password,full_api), shell=True))
    return result

def get_latest_req_stat():
    cluster_requests = am_req(api_name='requests')
    latest_cluster_req = cluster_requests['items'][-1]['href']
    return (am_req(full_api=latest_cluster_req)['Requests']['request_status'])

def get_config(config_name, set_file=None):
    if set_file:
        return check_output('/var/lib/ambari-server/resources/scripts/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c {4} -f {5}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, config_name, set_file), shell=True)
    else:
        return check_output('/var/lib/ambari-server/resources/scripts/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c {4}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, config_name), shell=True)

def get_spark_defaults():
    try:
        spark_defaults =check_output('/var/lib/ambari-server/resources/scripts/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c spark-defaults -f {4}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, spark_def_json), shell=True)
        return ('spark-defaults')
    except:
        spark_defaults = check_output('/var/lib/ambari-server/resources/scripts/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a get -c spark2-defaults -f {4}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, spark_def_json), shell=True)
        return ('spark2-defaults')

def restart_services():
    call('curl -u {0}:\'{1}\' -i -H \'X-Requested-By: ambari\' -X POST -d \'{{\"RequestInfo\": {{\"command\":\"RESTART\",\"context\" :\"Unravel request: Restart Services\",\"operation_level\":\"host_component\"}},\"Requests/resource_filters\":[{{\"hosts_predicate\":\"HostRoles/stale_configs=true\"}}]}}\' http://{2}:8080/api/v1/clusters/{3}/requests > /tmp/Restart.out 2> /tmp/Restart.err < /dev/null &'.format(argv.username, argv.password, argv.am_host, argv.cluster_name),shell=True)

def update_config(config_name,config_key=None,config_value=None, set_file=None):
    try:
        if set_file:
            return check_output('/var/lib/ambari-server/resources/scripts/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a set -c {4} -f {5}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, config_name, set_file), shell=True)
        else:
            return check_output('/var/lib/ambari-server/resources/scripts/configs.py -l {0} -u {1} -p \'{2}\' -n {3} -a set -c {4} -k {5} -v {6}'.format(argv.am_host, argv.username, argv.password, argv.cluster_name, config_name, config_key, config_value), shell=True)
    except:
        print('\Update %s configuration failed' % config_name)

core_site = get_config('core-site')
hdfs_url = json.loads(core_site[core_site.find('properties\":')+13:])['fs.defaultFS']
hive_env_content = 'export AUX_CLASSPATH=${AUX_CLASSPATH}:/usr/local/unravel_client/unravel-hive-1.2.0-hook.jar'
hadoop_env_content = 'export HADOOP_CLASSPATH=${HADOOP_CLASSPATH}:/usr/local/unravel_client/unravel-hive-1.2.0-hook.jar'
hive_site_configs = {'hive.exec.driver.run.hooks': 'com.unraveldata.dataflow.hive.hook.HiveDriverHook',
                    'com.unraveldata.hive.hdfs.dir': '/user/unravel/HOOK_RESULT_DIR',
                    'com.unraveldata.hive.hook.tcp': 'true',
                    'com.unraveldata.host':argv.unravel}
spark_defaults_configs={'spark.eventLog.dir':hdfs_url + '/var/log/spark/apps',
                        'spark.history.fs.logDirectory':hdfs_url + '/var/log/spark/apps',
                        'spark.unravel.server.hostport':argv.unravel+':4043',
                        'spark.driver.extraJavaOptions':'-Dcom.unraveldata.client.rest.shutdown.ms=300 -javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=config=driver,libs=spark-%s.%s' % (argv.spark_ver[0],argv.spark_ver[1]),
                        'spark.executor.extraJavaOptions':'-Dcom.unraveldata.client.rest.shutdown.ms=300 -javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=config=executor,libs=spark-%s.%s' % (argv.spark_ver[0],argv.spark_ver[1])}
mapred_site_config = '-javaagent:/usr/local/unravel-agent/jars/btrace-agent.jar=libs=mr -Dunravel.server.hostport=%s:4043' % argv.unravel

def main():
    print('HDFS_URL: ' + hdfs_url)
    print('Hive-env: ' + hive_env_content)
    print('Hadoop-env: ' + hadoop_env_content)
    print('hive-site: ' + hive_site_configs)
    print('spark-defaults: ' + spark_defaults_configs)
    print('mapred-site: ' + mapred_site_config)
    sleep(30)
    print('Checking Ambari Operations')
    while(get_latest_req_stat() not in ['COMPLETED','FAILED']):
        print('Operations Status:' + get_latest_req_stat())
        sleep(30)
    print('All Operations are completed, Comparing configs')
    # spark-default
    spark_def_ver = get_spark_defaults()
    with open(spark_def_json, 'r') as f:
        spark_def = f.read()
        f.close()
    if all(x in spark_def for _,x in spark_defaults_configs.iteritems()):
        print(get_spark_defaults() + '\n\nSpark Config is correct')
    else:
        print('Spark Config is not correct')
        new_spark_def = json.loads('{' + spark_def + '}')
        for key,val in spark_defaults_configs.iteritems():
            new_spark_def['properties'][key] = val
        with open(spark_def_json, 'w') as f:
            f.write(json.dumps(new_spark_def)[1:-1])
            f.close()
        update_config(spark_def_ver, set_file=spark_def_json)
    sleep(5)
    # hive-env
    get_config('hive-env', set_file=hive_env_json)
    with open(hive_env_json,'r') as f:
        hive_env = f.read()
        f.close()
    if hive_env_content.split(' ')[1] in hive_env:
        print('\nAUX_CLASSPATH is in hive')
    else:
        print('\nAUX_CLASSPATH is missing')
        # print(hive_env)
        content = hive_env[hive_env.find('\"content\": \"')+12:hive_env.find('{% endif %}\"')+11]
        new_content = json.dumps(content + '\n' + hive_env_content)[1:-1]
        sleep(2)
        with open(hive_env_json,'w') as f:
            f.write(hive_env.replace(content, new_content, 1))
            f.close()
        update_config('hive-env', set_file=hive_env_json)
        sleep(5)
    # hive-site
    hive_site = get_config('hive-site')
    if all(x in hive_site for _,x in hive_site_configs.iteritems()):
        print('\nCustom hive-site configs are correct')
    else:
        print('\nCustom hive-site configs are missing')
    sleep(5)
    # hadoop-env
    get_config('hadoop-env', set_file=hadoop_env_json)
    with open(hadoop_env_json,'r') as f:
        hadoop_env = f.read()
        f.close()
    if hadoop_env.find(hadoop_env_content.split(' ')[1]) > -1:
        print('\nHADOOP_CLASSPATH is correct')
    else:
        print('\nHADOOP_CLASSPATH is missing, updating')
        # print(hadoop_env)
        content = hadoop_env[hadoop_env.find('\"content\": \"')+12:hadoop_env.find('{% endif %}\",')+11]
        new_content = json.dumps(content + '\n' + hadoop_env_content)[1:-1]
        sleep(2)
        with open(hadoop_env_json,'w') as f:
            f.write(hadoop_env.replace(content, new_content, 1))
            f.close()
        update_config('hadoop-env', set_file=hadoop_env_json)
        sleep(5)
    # mapred-site
    get_config('mapred-site',set_file=mapred_site_json)
    with open(mapred_site_json,'r') as f:
        mapred_site = json.loads('{' + f.read() + '}')
        f.close()
    # print(mapred_site)
    if mapred_site_config in mapred_site['properties']['yarn.app.mapreduce.am.command-opts']:
        print('\nyarn.app.mapreduce.am.command-opts correct')
    else:
        print('\nyarn.app.mapreduce.am.command-opts missing')
        mapred_site['properties']['yarn.app.mapreduce.am.command-opts'] += ' ' + mapred_site_config
        with open(mapred_site_json,'w') as f:
            f.write(json.dumps(mapred_site)[1:-1])
            f.close()
        update_config('mapred-site', set_file=mapred_site_json)

    restart_services()

if __name__ == '__main__':
    main()
