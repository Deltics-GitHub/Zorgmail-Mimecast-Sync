import requests
import configparser
import argparse
import logging
import re
import time
def argsparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="be verbose", action="store_true")
    parser.add_argument("-c", "--config_file", help="config file", required=True)
    return parser.parse_args()

def get_zorgmail_domains(config):
    """
    Get Zorgmail domains from webpage
    :param config: Zorgmail domainbook url
    :return: List of Zorgmail relay domains
    """
    response = requests.get(config['default']['domainbook_url'])
    if response.status_code == 200:
        logging.debug(f'Status code: {response.status_code}')
        logging.info(f'successfully obtained Zorgmail domain list')
        logging.debug(response.text)
        webpage = response.content
        webpage = webpage.decode("utf-8")
        response.close()
        webpage = re.sub("###.*\n", '', webpage)
        zorgmail_domains = webpage.split()
        return zorgmail_domains
    else:
        logging.error(f'Status code: {response.status_code}')
        logging.error(response.text)
        print("Please check your credentials")
        exit(1)

def get_token(config):
    """
    Get OAuth token from Mimecast
    :param config:  client_id, client_secret, base_url
    :return: bearer_token
    """
    url = f"https://{config['default']['base_url']}/oauth/token"
    payload = f"client_id={config['default']['client_id']}&client_secret={config['default']['client_secret']}&grant_type=client_credentials"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code == 200:
        logging.debug(f'Status code: {response.status_code}')
        logging.info(f'successfully obtained token')
        return response.json()['access_token']

    else:
        logging.error(f'Status code: {response.status_code}')
        logging.error(response.text)
        print("Please check your credentials")
        exit(1)

def get_groups(config, bearer_token):
    """
    Get folders from Mimecast Directory
    :param config: client_id, client_secret, base_url
    :param bearer_token: OAuth token
    :return: folder_id
    """
    url = f"https://{config['default']['base_url']}/api/directory/find-groups"
    headers = {'Authorization':f"Bearer {bearer_token}"}
    payload = {
        'meta': {
            'pagination': {
                'pageSize': 25,
                'pageToken': ''
            }
        },
        'data': [
            {
                'query': config['default']['group'],
                'source': 'cloud'
            }
        ]
    }
    response = requests.post(url, headers=headers, data=str(payload))
    if response.status_code == 200:
        logging.debug(f'Status code: {response.status_code}')
        logging.debug(f'Successfully obtained group ID\'s')
        # Only get Zorgmail group
        logging.debug(f"Found the following groups: {response.json()['data'][0]['folders']}")
        return response.json()['data'][0]['folders'][0]['id']
    else:
        logging.error(f'Status code: {response.status_code}')
        logging.error(response.text)
        print("Please check the log file")
        exit(1)

def get_group_members(config, bearer_token, folder_id):
    """
    Get group members from Mimecast folder
    :param config: client_id, client_secret, base_url
    :param bearer_token: OAuth token
    :param folder_id: ID of Mimcast folder
    :return: List of domains
    """
    url = f"https://{config['default']['base_url']}/api/directory/get-group-members"
    headers = {'Authorization': f"Bearer {bearer_token}"}
    next = ''
    domains = []
    page = 1
    while True:
        payload = {
            'meta': {
                'pagination': {
                    'pageSize': 100,
                    'pageToken': next
                }
            },
            'data': [
                {
                    'id': folder_id
                }
            ]
        }
        response = requests.post(url, headers=headers, data=str(payload))
        if response.status_code == 200:
            logging.debug(f'Status code: {response.status_code}')
            logging.debug(f'Page: {page}')
            page +=1
            groupMembers = response.json()['data'][0]['groupMembers']
            for address in groupMembers:
                logging.debug(f"Added: {address['domain']}")
                domains.append(address['domain'])
            if ('next' in response.json()['meta']['pagination']):
                next = response.json()['meta']['pagination']['next']
            else:
                break
        else:
            logging.error(f'Status code: {response.status_code}')
            logging.error(f'Error getting group members')
            logging.error(response.text)
            exit(1)
    return domains

def remove_domains(config, bearer_token, folder_id, remove):
    """
    Remove domains that are no longer in the domainbook from profile group
    :param config: client_id, client_secret, base_url
    :param bearer_token: OAuth token
    :param folder_id: Id of the Profile Groups
    :return:
    """
    url = f"https://{config['default']['base_url']}/api/directory/remove-group-member"
    headers = {'Authorization': f"Bearer {bearer_token}"}
    for domain in remove:
        payload = {
            'data': [
                {
                    'id': folder_id,
                    'domain': domain
                }
            ]
        }
        response = requests.post(url=url, headers=headers, data=str(payload))
        if response.status_code == 200:
            logging.debug(f'Successfully removed {domain}')
        else:
            logging.error(f'Status code: {response.status_code}')
            logging.error(response.text)
            print("Please check the log file")
            exit(1)

def add_domains(config, bearer_token, folder_id, add):
    """
    Add domains to profile group
    :param config: client_id, client_secret, base_url
    :param bearer_token: OAuth token
    :param folder_id: Id of the Profile Groups
    :return:
    """
    url = f"https://{config['default']['base_url']}/api/directory/add-group-member"
    headers = {'Authorization': f"Bearer {bearer_token}"}
    payload = {'data': []}
    for i, domain in enumerate(add, start=1):
        print(f"{i}/{len(add)} - {domain}", end='\r', flush=True)

        test = {'id': folder_id, 'domain': domain}
        payload['data'].append(test)

        # Check if the batch size is reached or it's the last iteration
        if i % 500 == 0 or i == len(add):
            response = requests.post(url=url, headers=headers, json=payload)

            if response.status_code == 200:
                logging.debug(f'Successfully added {i} domains')
            elif response.status_code == 429:
                logging.warning("Rate limit: waiting a few seconds...")
                print(response.headers)
                try:
                    if int(response.headers['x-ratelimit-reset']) <= 1:
                        print("sleep: " + response.headers['x-ratelimit-reset'])
                        time.sleep(int(response.headers['x-ratelimit-reset']) + 1)
                except KeyError:
                    pass
                else:
                    time.sleep(10)

            # Reset payload for the next batch
            payload = {'data': []}

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    args = argsparser()

    if args.verbose:
        logging.basicConfig(filename=f'{args.config_file}.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
    else:
        logging.basicConfig(filename=f'{args.config_file}.log', filemode='w',
                            format='%(name)s - %(levelname)s - %(message)s', level=logging.INFO)

    # Define config file
    config = configparser.ConfigParser()
    config.read(args.config_file)

    exclude_list = config['default']['exclude']
    exclude = exclude_list.split()

    # Get OAuth token
    bearer_token = get_token(config)

    # Get zorgmail domains
    zorgmail_domains = get_zorgmail_domains(config)

    # Get Profile groups
    folder_id = get_groups(config, bearer_token)

    # Get current domains in profile group
    domains = get_group_members(config, bearer_token, folder_id)

    # Remove old domains and excluded domain from list of domains
    remove = list(set(domains) - set(zorgmail_domains))
    remove = list(set(remove) | set(exclude))
    logging.info(f"Removing {len(remove)} domains:")
    logging.info('\n '.join(remove))

    # Add new domains to list of domains
    add = list(set(zorgmail_domains) - set(domains))
    add = list(set(add) - set(exclude))

    logging.info(f"Adding {len(add)} domains:")
    logging.info('\n'.join(add))

    # Remove old domains
    print(f"Removing {len(remove)} domains")
    remove_domains(config, bearer_token, folder_id, remove)

    # Add new domains
    print(f"Adding {len(add)} domains")
    add_domains(config, bearer_token, folder_id, add)




