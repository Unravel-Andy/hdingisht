#! /bin/bash

################################################################################################
# Unravel for HDInsight Bootstrap Script                                                       #
#                                                                                              #
# The bootstrap script log is located at /tmp/unravel                                          #
################################################################################################
[ -z "$TMP_DIR" ] && export TMP_DIR=/tmp/unravel
if [ ! -d $TMP_DIR ]; then
    mkdir -p $TMP_DIR
    chmod a+rw $TMP_DIR
fi

SENSOR_DIR=/usr/local

echo "Downloading unravel-sensor.tar.gz\n"
wget -O $TMP_DIR/unravel-sensor.tar.gz https://github.com/unravel-data/public/raw/master/hdi/unravel-azure/unravel-sensor.tar.gz

if [ -z $? ];then
    echo "unravel-sensor.tar.gz Downloaded\n"
else
    echo "unravel-sensor.tar.gz download failed"
    exit 1
fi

echo "Extracting unravel-sensor"
tar -zxvf $TMP_DIR/unravel-sensor.tar.gz

if [ -d $SENSOR_DIR/unravel-agent ] && [ -d $SENSOR_DIR/unravel_client ]; then
    echo "Deploy Sensor successed"
else echo "Deploy Sensor Failed"
fi
