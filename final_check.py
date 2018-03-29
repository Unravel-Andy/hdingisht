from subprocess import call, check_output
import urllib2,base64,json,argparse,sys
from time import sleep
log_dir='/tmp/unravel/'
sys.stdout = open(log_dir + 'final_check.out','w')
call('( crontab -l | grep -v -F \'python %sfinal_check.py\' ) | crontab -' % log_dir ,shell=True)
parser = argparse.ArgumentParser()
parser.add_argument('-host','--unravel-host', help='Unravel Server hostname', dest='unravel', required=True)
parser.add_argument('-user','--username', help='ambari username', required=True)
parser.add_argument('-pass','--password', help='ambari password', required=True)
parser.add_argument('-c','--cluster_name', help='ambari cluster name', required=True)
parser.add_argument('-s','--spark_ver', help='spark version', required=True)
argv = parser.parse_args()
username = argv.username#'hdinsightwatchdog'
password = argv.password#'0-!dA0{7&svLAB'
cluster_name = argv.cluster_name#'ctest21'
def am_req(api_name=None, full_api=None):
    if api_name:
        result = json.loads(check_output('curl -u {0}:\'{1}\' -s -H \'X-RequestedBy:ambari\' -X GET http://localhost:8080/api/v1/clusters/{2}/{3}'.format(username,password,cluster_name,api_name), shell=True))
    elif full_api:
        result = json.loads(check_output('curl -u {0}:\'{1}\' -s -H \'X-RequestedBy:ambari\' -X GET {2}'.format(username,password,full_api), shell=True))
    return result
def get_latest_req_stat():
    cluster_requests = am_req(api_name='requests')
    latest_cluster_req = cluster_requests['items'][-1]['href']
    return (am_req(full_api=latest_cluster_req)['Requests']['request_status'])
def get_spark_defaults():
    try:
        spark_defaults =check_output('/var/lib/ambari-server/resources/scripts/configs.py -l localhost -u {0} -p \'{1}\' -n {2} -a get -c spark-defaults'.format(username, password,cluster_name), shell=True)
    except:
        spark_defaults = check_output('/var/lib/ambari-server/resources/scripts/configs.py -l localhost -u {0} -p \'{1}\' -n {2} -a get -c spark2-defaults'.format(username, password,cluster_name), shell=True)
    return (spark_defaults)
def main():
    sleep(30)
    while(get_latest_req_stat() != 'COMPLETED'):
        print(get_latest_req_stat())
        sleep(10)
    if get_spark_defaults().find('/var/log/spark') > -1:
        print('Spark Config is correct')
    else:
        print('Spark Config is not correct rerun unravel_hdi_bootstrap.sh')
        call('wget https://raw.githubusercontent.com/adrian-unraveldata/azurecfg/master/cfg/unravel_hdi_bootstrap.sh',shell=True)
        call(['chmod', '+x', 'unravel_hdi_bootstrap.sh'])
        call('./unravel_hdi_bootstrap.sh --unravel-server %s --spark-version %s' % (argv.unravel, argv.spark_ver),shell=True)
if __name__ == '__main__':
    main()
