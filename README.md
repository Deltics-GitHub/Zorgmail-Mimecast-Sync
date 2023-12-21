# Zorgmail Mimecast Sync

This is a script used for updating the Mimecast profile group with the latest Zorgmail domainbook using the Mimcast API 2.0.  

# How to run
1. Create a directory /opt/update_mimecast_zorgdomains and place the files main.py and rename the config file to config.conf in this directory.  
2. Install python packages `pip3 install -r requirements.txt`  
3. Change the information in the config.conf file and fill in your secret_id and secret_key.
Also add your domains to the exclude list, so internal mail will not be routed through Zorgmail.

## Cronjob
Create a crontab with the information provided in the cron.txt file. (The user should have permissions to execute the script).  
`0 4 * * * /opt/update_mimecast_zorgdomains/main.py -c /opt/update_mimecast_zorgdomains/config.conf`