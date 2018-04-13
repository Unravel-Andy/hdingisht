## Unravel HDInsight Application Startup Scripts

### hdi_premises_sensor_deploy_.sh
Requirement: All head, worker, edge node need to run this script either via HDInsight Script Action or manually

Usage: `./hdi_premises_sensor_deploy_.sh`
1. Download Sensor tar.gz file from https://github.com/unravel-data/public/raw/master/hdi/unravel-azure/unravel-sensor.tar.gz
2. Extract Sensor tar.gz file to /usr/local/


### hdi_onpremises_bootstrap.sh
Requirement: The script need to be ran as sudo

Usage: `sudo ./hdi_onpremises_bootstrap.sh` or `sudo ./hdi_onpremises_bootstrap.sh uninstall`
1. Download `hdi_onpremises_setup.py` from to /tmp/unravel/
2. Run `hdi_onpremises_setup.py` in the background (either install or uninstall)


### hdi_onpremises_setup.py
Requirement: The script need to be ran as sudo

Usage: `sudo python hdi_onpremises_setup.py` or `sudo python hdi_onpremises_setup.py -uninstall`
1. Download `configs.py` from to /tmp/unravel/

 ~~2. Download `hdi_premises_sensor_deploy_.sh` and run as an Ambari task to deploy sensor on all hosts~~
2. Get Hive and Spark version via `/usr/bin/hive --version` and `spark-submit --version` based on what spark service is installed in Ambari
3. Get Edge node host via `hostname -i`
4. Fill in all the configurations and compare with Ambari Configuration, update configuration if not exist/correct
5. For uninstall, Unravel Configuration will be removed from Ambari Configuration


### configs.py
For usage check:  https://cwiki.apache.org/confluence/display/AMBARI/Modify+configurations#Modifyconfigurations-Editconfigurationusingconfigs.py
