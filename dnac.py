"""
A module to perform IP to hostname resolution of network device,
utilizing Cisco DNA Center platform Northbound API (Intent).
"""
import re
import time

from ipaddress import IPv4Address
from ipaddress import AddressValueError

import requests
from requests.auth import HTTPBasicAuth

class DNACHandler():
    """
    The class instance should be initialized providing hostname without
    protocol (e.g. sandboxdnac.cisco.com)
    """
    def __init__(self, hostname):

        self.hostname = hostname
        self.token = None

    def get_token(self, username, password):
        """Retrieve token from DNAC and assign to class attribute"""
        url = "https://" + self.hostname + "/api/system/v1/auth/token"
        auth = HTTPBasicAuth(username=username, password=password)
        headers = {"content-type": "application/json"}

        try:
            response = requests.post(url, auth=auth, headers=headers, \
                                    verify=False)
        except requests.exceptions.ConnectionError:
            print("Device down or not responding.")
            return 1

        json_data = response.json()

        if "error" in json_data:
            print("Error in response.\n%s" % response.text)
            return 1

        self.token = json_data["Token"]

        return 0

    def send_get(self, path):
        """Send GET request against specified path"""
        url = "https://" + self.hostname + path
        headers = {"content-type": "application/json",
                   "x-auth-token": self.token}

        while True:
            try:
                response = requests.get(url, headers=headers, verify=False)
            except requests.exceptions.ConnectionError:
                print("Device down or not responding.")
                return 1

            # Handle API's rate limiting
            if response.status_code == 429:
                wait_time = response.headers.get("Retry-After", 60)
                print("Rate limit hit. Waiting %s seconds." % wait_time)
                time.sleep(int(wait_time))
            else:
                # We only want JSON response
                try:
                    json_response = response.json()
                except ValueError:
                    print("Not JSON response. Data: \n%s" % response.text)
                    return 1

                return json_response

    def get_hostname_from_ip(self, ip_address):
        """
        Return deviceId using 'Get Interface by IP' REST API call
        Return hostname using 'Get Device by ID' REST API call
        """
        hostname = None

        path = "/dna/intent/api/v1/interface/ip-address/" + ip_address

        json_data = self.send_get(path)

        if isinstance(json_data["response"], dict):
            hostname = None
        else:
            parent_id = json_data["response"][0]["deviceId"]
            path_parent = "/dna/intent/api/v1/network-device/" + parent_id
            json_data_device = self.send_get(path_parent)
            hostname = json_data_device["response"]["hostname"]

        return hostname

    def validate_ip(self, text):
        """Confirm string is valid IP address"""
        try:
            IPv4Address(text)
            return True
        except AddressValueError:
            return False

        return False

    def process_line(self, line):
        """
        For each IP address in the line, find corresponding IP address of the device.
        Replace IP address with hostname reported by DNAC.
        """
        regex_groups = re.findall("\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", line)
        if regex_groups:
            for elem in regex_groups:
                if self.validate_ip(elem):
                    hostname = self.get_hostname_from_ip(elem)
                    if hostname:
                        line = line.replace(elem, hostname)
            return line

        return line

    def process_text(self, text):
        """Process text data, line by line"""
        data = []
        text_list = text.split("\n")

        for elem in text_list:
            line = self.process_line(elem)
            data.append(line)

        return "\n".join(data)
