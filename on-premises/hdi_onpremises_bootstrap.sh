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

SCRIPT_URL="https://raw.githubusercontent.com/Unravel-Andy/hdingisht/test/on-premises/hdi_onpremises_setup.py"

echo -e "\nDownloading Setup Script\n"
wget -O $TMP_DIR/hdi_onpremises_setup.py $SCRIPT_URL
if [ $? -eq 0 ];then
    echo -e "\nDownload Successed\n"
    sleep 5
    echo -e "\nRunning Setup Script in the background\n"
    if [ $1 -eq 'uninstall' ];then 
        nohup python $TMP_DIR/hdi_onpremises_setup.py uninstall> $TMP_DIR/hdi_onpremises_setup.log 2>$TMP_DIR/hdi_onpremises_setup.err &
    else
        nohup python $TMP_DIR/hdi_onpremises_setup.py > $TMP_DIR/hdi_onpremises_setup.log 2>$TMP_DIR/hdi_onpremises_setup.err &
    fi
else
    echo -e "\nDownload Failed\n"
    exit 1
fi
