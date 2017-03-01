import pprint
import logging
import logging.handlers
import json
from collections import OrderedDict
from time import sleep, time
from io import StringIO
import pkg_resources
import requests
import os
from insteonlocal.Switch import Switch
from insteonlocal.Group import Group
from insteonlocal.Dimmer import Dimmer
from insteonlocal.Fan import Fan

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>

# Todo:
# error handling
# linking devices
# scene management
# double tap scenes
# switch on updates/broadcasts

CACHE_TTL = 30 #30 seconds
CACHE_FILE = '.state'

class Hub(object):
    """Class for local control of insteon hub"""
    def __init__(self, ip_addr, username, password, port="25105", timeout=10, logger=None):
        self.ip_addr = ip_addr
        self.username = username
        self.password = password
        self.port = str(port)
        self.http_code = 0
        self.timeout = timeout

        self.buffer_status = OrderedDict()

        json_cats = pkg_resources.resource_string(__name__, 'data/device_categories.json')
        json_cats_str = json_cats.decode('utf-8')
        self.device_categories = json.loads(json_cats_str)

        json_models = pkg_resources.resource_string(__name__, 'data/device_models.json')
        json_models_str = json_models.decode('utf-8')
        self.device_models = json.loads(json_models_str)

        self.hub_url = 'http://' + self.ip_addr + ':' + self.port

        if logger is None:
            self.logger = logging.getLogger('')
            self.logger.setLevel(logging.INFO)
        else:
            self.logger = logger


    def brightness_to_hex(self, level):
        """Convert numeric brightness percentage into hex for insteon"""
        level_int = int(level)
        new_int = int((level_int * 255)/100)
        new_level = format(new_int, '02X')
        self.logger.debug("brightness_to_hex: %s to %s", level, str(new_level))
        return str(new_level)


    def post_direct_command(self, command_url):
        """Send raw command via post"""
        self.logger.info("post_direct_command: %s", command_url)
        req = requests.post(command_url, timeout=self.timeout,
                            auth=requests.auth.HTTPBasicAuth(self.username,
                                                             self.password))
        self.http_code = req.status_code
        req.raise_for_status()
        return req


    def get_direct_command(self, command_url):
        """Send raw command via get"""
        self.logger.info("get_direct_command: %s", command_url)
        req = requests.get(command_url, timeout=self.timeout,
                           auth=requests.auth.HTTPBasicAuth(self.username,
                                                            self.password))
        self.http_code = req.status_code
        req.raise_for_status()
        return req


    def direct_command(self, device_id, command, command2, extended_payload=None):
        """Wrapper to send posted direct command and get response. Level is 0-100.
        extended_payload is 14 bytes/28 chars"""
        extended_payload = extended_payload or ''
        if not extended_payload:
            msg_type = '0'
            msg_type_desc = 'Standard'
        else:
            msg_type = '1'
            msg_type_desc = 'Extended'
            extended_payload = extended_payload.ljust(28, '0')

        self.logger.info("direct_command: Device: %s Command: %s Command 2: %s "
                         "MsgType: %s", device_id, command, command2, msg_type_desc)
        device_id = device_id.upper()
        command_url = (self.hub_url + '/3?' + "0262"
                       + device_id + msg_type + "F"
                       + command + command2 + extended_payload + "=I=3")
        return self.post_direct_command(command_url)


    def direct_command_hub(self, command):
        """Send direct hub command"""
        self.logger.info("direct_command_hub: Command %s", command)
        command_url = (self.hub_url + '/3?' + command + "=I=3")
        return self.post_direct_command(command_url)


    def direct_command_short(self, command):
        """Wrapper for short-form commands (doesn't need device id or flags byte)"""
        self.logger.info("direct_command_short: Command %s", command)
        command_url = (self.hub_url + '/3?' + command + "=I=0")
        return self.post_direct_command(command_url)


    def get_linked(self):
        """Get a list of currently linked devices from the hub"""
        linked_devices = {}
        self.logger.info("\nget_linked")

        #todo instead of sleep, create loop to keep checking buffer
        self.direct_command_hub('0269')
        sleep(1)
        self.get_buffer_status()
        msgs = self.buffer_status.get('msgs', [])
        for entry in msgs:
            im_code = entry.get('im_code', '')
            #self.logger.info("get_linked entry {}".format(pprint.pformat(entry)))

            if im_code == '57':
                device_id = entry.get('id_high', '') + entry.get('id_mid', '') \
                            + entry.get('id_low', '')
                group = entry.get('group', '')
                if device_id not in linked_devices:
                    dev_info = self.id_request(device_id)
                    dev_cat = dev_info.get('id_high', '')
                    dev_sub_cat = dev_info.get('id_mid', '')
                    dev_cat_record = self.get_device_category(dev_cat)
                    if dev_cat_record and 'name' in dev_cat_record:
                        dev_cat_name = dev_cat_record['name']
                        dev_cat_type = dev_cat_record['type']
                    else:
                        dev_cat_name = 'unknown'
                        dev_cat_type = 'unknown'

                    linked_dev_model = self.get_device_model(dev_cat, dev_sub_cat)
                    if 'name' in linked_dev_model:
                        dev_model_name = linked_dev_model['name']
                    else:
                        dev_model_name = 'unknown'

                    if 'sku' in linked_dev_model:
                        dev_sku = linked_dev_model['sku']
                    else:
                        dev_sku = 'unknown'

                    self.logger.info("get_linked: Got first device: %s group %s "
                                     "cat type %s cat name %s dev model name %s",
                                     device_id, group, dev_cat_type,
                                     dev_cat_name, dev_model_name)
                    linked_devices[device_id] = {
                        'cat_name': dev_cat_name,
                        'cat_type': dev_cat_type,
                        'model_name' : dev_model_name,
                        'cat': dev_cat,
                        'sub_cat': dev_sub_cat,
                        'sku': dev_sku,
                        'group': []
                    }

                linked_devices[device_id]['group'].append(group)

        while self.buffer_status['success']:
            self.direct_command_hub('026A')
            sleep(1)
            self.get_buffer_status()
            msgs = self.buffer_status.get('msgs', [])
            for entry in msgs:
                im_code = entry.get('im_code', '')
                if im_code == '57':
                    device_id = entry.get('id_high', '') + entry.get('id_mid', '') \
                                + entry.get('id_low', '')
                    group = entry.get('group', '')

                    if device_id not in linked_devices:
                        dev_info = self.id_request(device_id)
                        dev_cat = dev_info.get('id_high', '')
                        dev_sub_cat = dev_info.get('id_mid', '')
                        dev_cat_record = self.get_device_category(dev_cat)
                        if dev_cat_record and 'name' in dev_cat_record:
                            dev_cat_name = dev_cat_record['name']
                            dev_cat_type = dev_cat_record['type']
                        else:
                            dev_cat_name = 'unknown'
                            dev_cat_type = 'unknown'

                        linked_dev_model = self.get_device_model(dev_cat, dev_sub_cat)
                        if 'name' in linked_dev_model:
                            dev_model_name = linked_dev_model['name']
                        else:
                            dev_model_name = 'unknown'

                        if 'sku' in linked_dev_model:
                            dev_sku = linked_dev_model['sku']
                        else:
                            dev_sku = 'unknown'

                        self.logger.info("get_linked: Got device: %s group %s "
                                         + "cat type %s cat name %s dev model name %s",
                                         device_id, group, dev_cat_type,
                                         dev_cat_name, dev_model_name)
                        linked_devices[device_id] = {
                            'cat_name': dev_cat_name,
                            'cat_type': dev_cat_type,
                            'model_name' : dev_model_name,
                            'cat': dev_cat,
                            'sub_cat': dev_sub_cat,
                            'sku': dev_sku,
                            'group': []
                        }

                    linked_devices[device_id]['group'].append(group)

        self.logger.info("get_linked: Final device list: %s", pprint.pformat(linked_devices))
        return linked_devices


    def get_device_category(self, cat):
        """Return the device category and name given the category id"""
        if cat in self.device_categories:
            return self.device_categories[cat]
        else:
            return False


    def get_device_model(self, cat, sub_cat, key=''):
        """Return the model name given cat/subcat or product key"""
        if cat + ':' + sub_cat in self.device_models:
            return self.device_models[cat + ':' + sub_cat]
        else:
            for i_key, i_val in self.device_models.items():
                if 'key' in i_val:
                    if i_val['key'] == key:
                        return i_val
            return False


    def id_request(self, device_id):
        """Get the device for the ID. ID request can return device type (cat/subcat),
        firmware ver, etc. Cat is status['is_high'], sub cat is status['id_mid']"""
        self.logger.info("\nid_request for device %s", device_id)
        device_id = device_id.upper()

        self.direct_command(device_id, '10', '00')

        sleep(2)

        status = self.get_buffer_status(device_id)

        return status


    def get_device_status(self, device_id, return_led=0, level=None):
        """Do a separate query to get device status. This can tell if device
        is on/off, lighting level, etc."""
        # status['responseCmd2'] is lighting level
        # responseCmd1 contains All-Link Database delta
        # if returnLED = 0. returns light level in responseCmd2
        # if returnLED = 1, returns LED Bit Flags in responseCmd1

        self.logger.info("\nget_device_status for device %s", device_id)
        device_id = device_id.upper()

        if not level:
            if return_led == 1:
                level = '01'
            else:
                level = '00'

        status = self.get_command_response_from_cache(device_id, '19', level)

        if not status:
            self.direct_command(device_id, '19', level)

            attempts = 1
            sleep(1)

            status = self.get_buffer_status(device_id)
            while 'success' not in status and attempts < 9:
                status = self.get_command_response_from_cache(device_id, '19', level)
                if not status:
                    if attempts % 3 == 0:
                        self.direct_command(device_id, '19', level)
                    else:
                        sleep(1)
                    status = self.get_buffer_status(device_id)
                attempts += 1

        return status

    def get_cache_from_file(self, deviceid):
        filename = deviceid + CACHE_FILE
        cache_loaded = False
        attempts = 0
        data = {}

        if not os.path.exists(filename):
            file = open(filename, "w+")
            json.dump({}, file)
            file.close()
            return {}

        while not cache_loaded:
            try:
                with open(filename) as cachefile:
                    data = json.load(cachefile)
                    cachefile.close()

                cache_loaded = True
                break
            except json.JSONDecodeError:
                self.logger.info("couldn't decode cachefile")
                if attempts >= 3:
                    cache_loaded = True
                else:
                    attempts += 1
        return data

    def write_cache_file(self, cache, device_id):
        filename = device_id + CACHE_FILE

        with open(filename + '.temp', 'w') as cachefile:
            json.dump(cache, cachefile)

        cachefile.close()

        if os.path.exists(filename):
            os.remove(filename)

        os.rename(filename + '.temp', filename)

    def get_command_response_from_cache(self, device_id, command, command2):
        """Gets response"""
        key = self.create_key_from_command(command, command2)
        command_cache = self.get_cache_from_file(device_id)

        if device_id not in command_cache:
            command_cache[device_id] = {}
            return False
        elif key not in command_cache[device_id]:
            return False

        response = command_cache[device_id][key]

        if response['ttl'] < int(time()):
            return response['response']
        else:
            return False

    def clear_device_command_cache(self, device_id):

        command_cache = self.get_cache_from_file(device_id)

        command_cache[device_id] = {}

        self.write_cache_file(command_cache, device_id)


    def set_command_response_from_cache(self, response, device_id, command, command2):
        """Sets response"""
        if not device_id:
            return False

        key = self.create_key_from_command(command, command2)
        ttl = int(time()) + CACHE_TTL

        command_cache = self.get_cache_from_file(device_id)

        if device_id not in command_cache:
            command_cache[device_id] = {}

        command_cache[device_id][key] = {'ttl': ttl, 'response': response}

        self.write_cache_file(command_cache, device_id)

    def create_key_from_command(self, command, command2):
        """gets key"""
        return command + command2

    def get_buffer_status(self, device_from=None):
        """Main method to read from buffer. Optionally pass in device to
        only get response from that device"""
        device_from = device_from or ''

        # only used if device_from passed in
        return_record = OrderedDict()
        return_record['success'] = False
        return_record['error'] = True

        command_url = self.hub_url + '/buffstatus.xml'
        self.logger.info("get_buffer_status: %s", command_url)

        response = self.get_direct_command(command_url)
        raw_text = response.text
        raw_text = raw_text.replace('<response><BS>', '')
        raw_text = raw_text.replace('</BS></response>', '')
        raw_text = raw_text.strip()
        buffer_length = len(raw_text)
        self.logger.info('get_buffer_status: Got raw text with size %s and contents: %s',
                         buffer_length, raw_text)

        if buffer_length == 202:
            # 2015 hub
            # the last byte in the buffer indicates where it stopped writing.
            # checking for text after that position would show if the buffer
            # has overlapped and allow ignoring the old stuff after
            buffer_end = raw_text[-2:]
            buffer_end_int = int(buffer_end, 16)
            raw_text = raw_text[0:buffer_end_int]
            self.logger.info('bufferEnd hex %s dec %s', buffer_end, buffer_end_int)
            self.logger.info('get_buffer_status: non wrapped %s', raw_text)

        self.buffer_status = OrderedDict()

        self.buffer_status['error'] = False
        self.buffer_status['success'] = True
        self.buffer_status['message'] = ''
        self.buffer_status['msgs'] = []

        buffer_contents = StringIO(raw_text)

        while True:

            msg = buffer_contents.read(4)
            if (len(msg) < 4) or (msg == '') or (msg == '0000'):
                break

            #im_start = msg[0:2]
            im_cmd = msg[2:4]

            response_record = OrderedDict()
            response_record['im_code'] = im_cmd

            # Standard Message Received
            if im_cmd == '50':
                msg = msg + buffer_contents.read(18)
                response_record['im_code_desc'] = 'Standard Message Received'
                response_record['raw'] = msg
                response_record['id_from'] = msg[4:10]
                # direct id high, group group_id, broadcast cat
                response_record['id_high'] = msg[10:12]
                # direct id mid, broadcast subcat
                response_record['id_mid'] = msg[12:14]
                # direct id low, broadcast firmware version
                response_record['id_low'] = msg[14:16]
                # 2 ack, 8 broadcast
                response_record['flag1'] = msg[16:17]
                # hop count B
                response_record['flag2'] = msg[17:18]
                # direct cmd, broadcast 01, status db delta
                response_record['cmd1'] = msg[18:20]
                # direct cmd 2, broadcast 00, status on level
                response_record['cmd2'] = msg[20:22]

            # Extended Mesage Received
            elif im_cmd == '51':
                msg = msg + buffer_contents.read(46)

                response_record['im_code_desc'] = 'Extended Message Received'
                response_record['raw'] = msg
                response_record['id_from'] = msg[4:10]
                # direct id high, group group_id, broadcast cat
                response_record['id_high'] = msg[10:12]
                # direct id mid, broadcast subcat
                response_record['id_mid'] = msg[12:14]
                # direct id low, broadcast firmware version
                response_record['id_low'] = msg[14:16]
                # 2 ack, 8 broadcast + hop count B
                response_record['flags'] = msg[16:18]
                # direct cmd, broadcast 01, status db delta
                response_record['cmd1'] = msg[18:20]
                # direct cmd 2, broadcast 00, status on level
                response_record['cmd2'] = msg[20:22]
                response_record['user_data_1'] = msg[22:24]
                response_record['user_data_2'] = msg[24:26]
                response_record['user_data_3'] = msg[26:28]
                response_record['user_data_4'] = msg[28:30]
                response_record['user_data_5'] = msg[30:32]
                response_record['user_data_6'] = msg[32:34]
                response_record['user_data_7'] = msg[34:36]
                response_record['user_data_8'] = msg[36:38]
                response_record['user_data_9'] = msg[38:40]
                response_record['user_data_10'] = msg[40:42]
                response_record['user_data_11'] = msg[42:44]
                response_record['user_data_12'] = msg[44:46]
                response_record['user_data_13'] = msg[46:48]
                response_record['user_data_14'] = msg[48:50]

            # X10 Received (not implemented)
            elif im_cmd == '52':
                self.logger.error('Not implemented handling of 0252 X10 Received')
                break

            # ALL-Linking Completed
            elif im_cmd == '53':
                msg = msg = buffer_contents.read(16)

                response_record['im_code_desc'] = 'ALL-Linking Completed'
                response_record['raw'] = msg
                response_record['link_status'] = msg[4:6]

                if response_record['link_status'] == '00':
                    response_record['link_status_desc'] = 'IM is Responder'
                elif response_record['link_status'] == '01':
                    response_record['link_status_desc'] = 'IM is Controller'
                elif response_record['link_status'] == 'FF':
                    response_record['link_status_desc'] = 'Link Deleted'

                response_record['group'] = msg[6:8]
                response_record['id_high'] = msg[8:10]
                response_record['id_mid'] = msg[10:12]
                response_record['id_low'] = msg[12:14]
                response_record['dev_cat'] = msg[14:16]
                response_record['dev_subcat'] = msg[16:18]
                response_record['dev_firmware_rev'] = msg[18:20] # or FF for newer devices

            # Button Event Report
            elif im_cmd == '54':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'Button Event Report'
                response_record['raw'] = msg
                response_record['report_type'] = msg[4:6]
                if response_record['report_type'] == "02":
                    response_record['report_type_desc'] = "IM's SET Button tapped"
                elif response_record['report_type'] == "03":
                    response_record['report_type_desc'] = "IM's SET Button held"
                elif response_record['report_type'] == "04":
                    response_record['report_type_desc'] = "IM's SET Button released after hold"
                elif response_record['report_type'] == "12":
                    response_record['report_type_desc'] = "IM's Button 2 tapped"
                elif response_record['report_type'] == "13":
                    response_record['report_type_desc'] = "IM's Button 2 held"
                elif response_record['report_type'] == "14":
                    response_record['report_type_desc'] = "IM's Button 2 released after hold"
                elif response_record['report_type'] == "22":
                    response_record['report_type_desc'] = "IM's Button 3 tapped"
                elif response_record['report_type'] == "23":
                    response_record['report_type_desc'] = "IM's Button 3 held"
                elif response_record['report_type'] == "24":
                    response_record['report_type_desc'] = "IM's Button 3 released after hold"

            # User Reset Detected
            elif im_cmd == '55':
                response_record['im_code_desc'] = 'User Reset Detected'
                response_record['raw'] = msg
                response_record['im_code_desc2'] = "User pushed and held IM's " \
                                                   "SET Button on power up"

            # ALL-Link Cleanup Failure Report
            elif im_cmd == '56':
                msg = msg + buffer_contents.read(10)

                response_record['im_code_desc'] = 'ALL-Link Cleanup Failure Report'
                response_record['raw'] = msg
                response_record['group'] = msg[4:6]
                # 01 means member did not acknlowedge all-link cleanup cmd
                response_record['ack'] = msg[6:8]
                response_record['id_high'] = msg[8:10]
                response_record['id_mid'] = msg[10:12]
                response_record['id_low'] = msg[12:14]

            # ALL-Link Record Response
            elif im_cmd == '57':
                msg = msg + buffer_contents.read(20)

                response_record['im_code_desc'] = 'ALL-Link Record Response'
                response_record['raw'] = msg
                response_record['flags'] = msg[4:6] # hub dev manual p 39
                response_record['group'] = msg[6:8]
                response_record['id_high'] = msg[8:10]
                response_record['id_mid'] = msg[10:12]
                response_record['id_low'] = msg[12:14]
                response_record['link_data_1'] = msg[14:16]
                response_record['link_data_2'] = msg[16:18]
                response_record['link_data_3'] = msg[18:20]

            # ALL-Link Cleanup Status Report
            elif im_cmd == '58':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'ALL-Link Cleanup Status Report'
                response_record['raw'] = msg
                response_record['cleanup_status'] = msg[4:6]
                if response_record['cleanup_status'] == '06':
                    response_record['cleanup_status_desc'] = 'ALL-Link Cleanup ' \
                                                            'sequence completed'
                elif response_record['cleanup_status'] == '15':
                    response_record['cleanup_status_desc'] = 'ALL-Link Cleanup ' \
                                                             'sequence aborted due ' \
                                                             'to INSTEON traffic'

            # Database Record Found
            elif im_cmd == '59':
                msg = msg + buffer_contents.read(18)

                response_record['im_code_desc'] = 'Database Record Found'
                response_record['raw'] = msg
                response_record['address_low'] = msg[4:6]
                response_record['record_flags'] = msg[6:8]
                response_record['group'] = msg[8:10]
                response_record['id_high'] = msg[10:12]
                response_record['id_mid'] = msg[12:14]
                response_record['id_low'] = msg[14:16]
                response_record['link_data_1'] = msg[16:18]
                response_record['link_data_2'] = msg[18:20]
                response_record['link_data_3'] = msg[20:22]

            # Get IM Info
            elif im_cmd == '60':
                msg = msg + buffer_contents.read(14)

                response_record['im_code_desc'] = 'Get IM Info'
                response_record['raw'] = msg
                response_record['id_high'] = msg[4:6]
                response_record['id_mid'] = msg[6:8]
                response_record['id_low'] = msg[8:10]
                response_record['dev_cat'] = msg[10:12]
                response_record['dev_subcat'] = msg[12:14]
                response_record['dev_firmware_rev'] = msg[14:16]
                response_record['ack_or_nak'] = msg[16:18] # 06 ack

            # Send ALL-Link Command
            elif im_cmd == '61':
                msg = msg + buffer_contents.read(8)

                response_record['im_code_desc'] = 'Send ALL-Link Command'
                response_record['raw'] = msg
                response_record['group'] = msg[4:6]
                response_record['cmd'] = msg[6:8]
                response_record['broadcast_cmd2'] = msg[8:10] # FF or 00
                response_record['ack_or_nak'] = msg[10:12] # 06 ack

            # Send Message (Pass through command to PLM)
            elif im_cmd == '62':
                msg = msg + buffer_contents.read(8)
                response_record['id'] = msg[4:10]
                response_record['flags'] = msg[10:12]

                # Standard Message
                if response_record['flags'][0] == '0':
                    response_record['im_code_desc'] = 'Send Standard Message'
                    msg = msg + buffer_contents.read(6)
                    response_record['cmd1'] = msg[12:14]
                    response_record['cmd2'] = msg[14:16]
                    response_record['ack_or_nak'] = msg[16:18] # 06 ack 15 nak

                # Extended Message
                elif response_record['flags'][0] == '1':
                    response_record['im_code_desc'] = 'Send Extended Message'
                    msg = msg + buffer_contents.read(34)
                    response_record['cmd1'] = msg[12:14]
                    response_record['cmd2'] = msg[14:16]
                    response_record['user_data_1'] = msg[16:18]
                    response_record['user_data_2'] = msg[18:20]
                    response_record['user_data_3'] = msg[20:22]
                    response_record['user_data_4'] = msg[22:24]
                    response_record['user_data_5'] = msg[24:26]
                    response_record['user_data_6'] = msg[26:28]
                    response_record['user_data_7'] = msg[28:30]
                    response_record['user_data_8'] = msg[30:32]
                    response_record['user_data_9'] = msg[32:34]
                    response_record['user_data_10'] = msg[34:36]
                    response_record['user_data_11'] = msg[36:38]
                    response_record['user_data_12'] = msg[38:40]
                    response_record['user_data_13'] = msg[40:42]
                    response_record['user_data_14'] = msg[42:44]
                    response_record['ack_or_nak'] = msg[44:46] # 06 ack 15 nak

                # Not implemented
                else:
                    self.logger.error('Not implemented, message flag %s' % response_record['flags'])

                response_record['raw'] = msg

            # Send X10 (not implemented)
            elif im_cmd == '63':
                self.logger.error('Not implemented handling of 0263 Send X10')
                break

            # Start ALL-Linking
            elif im_cmd == '64':
                msg = msg + buffer_contents.read(6)

                response_record['im_code_desc'] = 'Start ALL-Linking'
                response_record['raw'] = msg
                response_record['link_type'] = msg[4:6]

                if response_record['link_type'] == '00':
                    response_record['link_type_desc'] = 'IM is Responder'
                elif response_record['link_type'] == '01':
                    response_record['link_type_desc'] = 'IM is Controller'
                elif response_record['link_type'] == '03':
                    response_record['link_type_desc'] = 'IM is Either Responder ' \
                                                        'or Controller'
                elif response_record['link_type'] == 'FF':
                    response_record['link_type_desc'] = 'Link Deleted'

                response_record['group'] = msg[6:8]
                response_record['ack_or_nak'] = msg[8:10] # 06 ack 15 nak

            # Cancel ALL-Linking
            elif im_cmd == '65':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'Cancel ALL-Linking'
                response_record['raw'] = msg
                response_record['ack_or_nak'] = msg[4:6] # 06 ack 15 nak

            # Set Host Device Category
            elif im_cmd == '66':
                msg = msg + buffer_contents.read(8)

                response_record['im_code_desc'] = 'Set Host Device Category'
                response_record['raw'] = msg
                response_record['dev_cat'] = msg[4:6]
                response_record['dev_subcat'] = msg[6:8]
                response_record['dev_firmware_rev'] = msg[8:10] # or 00
                response_record['ack_or_nak'] = msg[10:12] # 06 ack 15 nak

            # Reset the IM
            elif im_cmd == '67':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'Reset the IM'
                response_record['raw'] = msg
                response_record['ack_or_nak'] = msg[4:6] # 06 ack 15 nak

            # Set INSTEON ACK Message Byte
            elif im_cmd == '68':
                msg = msg + buffer_contents.read(4)

                response_record['im_code_desc'] = 'Set INSTEON ACK Message Byte'
                response_record['raw'] = msg
                response_record['cmd2_data'] = msg[4:6]
                response_record['ack_or_nak'] = msg[6:8] # 06 ack 15 nak

            # Get First ALL-Link Record
            elif im_cmd == '69':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'Get First ALL-Link Record'
                response_record['raw'] = msg
                response_record['ack_or_nak'] = msg[4:6] # 06 ack 15 nak

            # Get Next ALL-Link Record
            elif im_cmd == '6A':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'Get Next ALL-Link Record'
                response_record['raw'] = msg
                response_record['ack_or_nak'] = msg[4:6] # 06 ack 15 nak

            # Set IM Configuration
            elif im_cmd == '6B':
                msg = msg + buffer_contents.read(4)

                response_record['im_code_desc'] = 'Set IM Configuration'
                response_record['raw'] = msg
                response_record['im_cfg_flags'] = msg[4:6]
                response_record['ack_or_nak'] = msg[6:8] # 06 ack 15 nak

            # Get ALL-Link Record for Sender
            elif im_cmd == '6C':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'Get ALL-Link Record for Sender'
                response_record['raw'] = msg
                response_record['ack_or_nak'] = msg[4:6] # 06 ack 15 nak

            # LED On
            elif im_cmd == '6D':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'LED On'
                response_record['raw'] = msg
                response_record['ack_or_nak'] = msg[4:6] # 06 ack 15 nak

            # LED Off
            elif im_cmd == '6E':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'LED Off'
                response_record['raw'] = msg
                response_record['ack_or_nak'] = msg[4:6] # 06 ack 15 nak

            # Manage ALL-Link Record
            elif im_cmd == '6F':
                msg = msg + buffer_contents.read(20)

                response_record['im_code_desc'] = 'Manage ALL-Link Record'
                response_record['raw'] = msg
                response_record['ctrl_flags'] = msg[4:6]
                response_record['record_flags'] = msg[6:8]
                response_record['group'] = msg[8:10]
                response_record['id_high'] = msg[10:12]
                response_record['id_mid'] = msg[12:14]
                response_record['id_low'] = msg[14:16]
                response_record['link_data_1'] = msg[16:18]
                response_record['link_data_2'] = msg[18:20]
                response_record['link_data_3'] = msg[20:22]
                response_record['ack_or_nak'] = msg[22:24] # 06 ack

            # Set INSTEON ACK Message Two Bytes
            elif im_cmd == '71':
                msg = msg + buffer_contents.read(6)

                response_record['im_code_desc'] = 'Set INSTEON ACK Message Two Bytes'
                response_record['raw'] = msg
                response_record['cmd1_data'] = msg[4:6]
                response_record['cmd2_data'] = msg[6:8]
                response_record['ack_or_nak'] = msg[8:10] # 06 ack

            # RF Sleep
            elif im_cmd == '72':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'RF Sleep'
                response_record['raw'] = msg
                response_record['ack_or_nak'] = msg[4:6] # 06 ack

            # Get IM Configuration
            elif im_cmd == '73':
                msg = msg + buffer_contents.read(8)

                response_record['im_code_desc'] = 'Get IM Configuration'
                response_record['raw'] = msg
                response_record['im_cfg_flags'] = msg[4:6]
                response_record['spare1'] = msg[6:8]
                response_record['spare2'] = msg[8:10]
                response_record['ack_or_nak'] = msg[10:12] # 06 ack

            # Cancel Cleanup
            elif im_cmd == '74':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'Cancel Cleanup'
                response_record['raw'] = msg
                response_record['ack_or_nak'] = msg[4:6] # 06 ack 15 nak

            # Read 8 bytes from Database
            elif im_cmd == '75':
                msg = msg + buffer_contents.read(30)

                response_record['im_code_desc'] = 'Read 8 bytes from Database'
                response_record['raw'] = msg
                response_record['db_addr_high'] = msg[4:6]
                response_record['db_addr_low'] = msg[6:8] # low nibble F, or 8
                response_record['ack_or_nak'] = msg[8:10] # 06 ack
                response_record['record'] = msg[10:34] # database record founnd
                                                       # response 12 bytes

            # Write 8 bytes to Database
            elif im_cmd == '76':
                msg = msg + buffer_contents.read(22)

                response_record['im_code_desc'] = 'Write 8 bytes to Database'
                response_record['raw'] = msg
                response_record['db_addr_high'] = msg[4:6]
                response_record['db_addr_low'] = msg[6:8] # low nibble F, or 8
                response_record['record_flags'] = msg[8:10]
                response_record['group'] = msg[10:12]
                response_record['id_high'] = msg[12:14]
                response_record['id_middle'] = msg[14:16]
                response_record['id_low'] = msg[16:18]
                response_record['link_data_1'] = msg[18:20]
                response_record['link_data_2'] = msg[20:22]
                response_record['link_data_3'] = msg[22:24]
                response_record['ack_or_nak'] = msg[24:26] # 06 ac

            # Beep
            elif im_cmd == '77':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'Beep'
                response_record['raw'] = msg
                response_record['ack_or_nak'] = msg[4:6] # 06 ack 15 nak

            # Set Status
            # IM reports Status in cmd2 of direct Status Request command (19)
            elif im_cmd == '78':
                msg = msg + buffer_contents.read(2)

                response_record['im_code_desc'] = 'Set Status'
                response_record['raw'] = msg
                response_record['ack_or_nak'] = msg[4:6] # 06 ack

            # Set Database Link Data for Next Link
            elif im_cmd == '79':
                msg = msg + buffer_contents.read(8)

                response_record['im_code_desc'] = 'Set Database Link Data for Next Link'
                response_record['raw'] = msg
                response_record['link_data_1'] = msg[4:6]
                response_record['link_data_2'] = msg[6:8]
                response_record['link_data_3'] = msg[8:10]
                response_record['ack_or_nak'] = msg[10:12] # 06 ack

            # Set Application Retries for New Links
            elif im_cmd == '7A':
                msg = msg + buffer_contents.read(4)

                response_record['im_code_desc'] = 'Set Application Retries for New Links'
                response_record['raw'] = msg
                response_record['num_retries'] = msg[4:6]
                response_record['ack_or_nak'] = msg[6:8] # 06 ack

            # Set RF Frequency Offset
            elif im_cmd == '7B':
                msg = msg + buffer_contents.read(4)

                response_record['im_code_desc'] = 'Set RF Frequency Offset'
                response_record['raw'] = msg
                response_record['rf_freq_offset'] = msg[4:6]
                response_record['ack_or_nak'] = msg[6:8] # 06 ack

            # Set Acknowledge for TempLinc Command (not implemented)
            elif im_cmd == '7C':
                self.logger.error('Not implemented handling of 027C Set '
                                  'Acknowledge for TempLinc command')
                break

            if response_record.get('ack_or_nak', '') == '15':
                self.buffer_status['error'] = True
                self.buffer_status['success'] = False
                self.buffer_status['message'] = 'Device returned nak'

            response_device_from = response_record.get('id_from', '')
            if device_from and device_from == response_device_from:
                return_record = response_record
                return_record['error'] = False
                return_record['success'] = True

            self.buffer_status['msgs'].append(response_record)

            if 'cmd1' in response_record and 'cmd2' in response_record:
                self.set_command_response_from_cache(response_record, device_from, response_record['cmd1'], response_record['cmd2'])

        # Tell hub to clear buffer
        self.clear_buffer()

        #pprint.pprint(self.buffer_status)
        self.logger.debug("get_buffer_status: %s", pprint.pformat(self.buffer_status))

        if device_from:
            return return_record

        return self.buffer_status


    def check_success(self, device_id, sent_cmd1, sent_cmd2):
        """Check if last command succeeded by checking buffer"""
        device_id = device_id.upper()

        self.logger.info('check_success: for device %s cmd1 %s cmd2 %s',
                         device_id, sent_cmd1, sent_cmd2)

        sleep(2)
        status = self.get_buffer_status(device_id)
        check_id = status.get('id_from', '')
        cmd1 = status.get('cmd1', '')
        cmd2 = status.get('cmd2', '')
        if (check_id == device_id) and (cmd1 == sent_cmd1) and (cmd2 == sent_cmd2):
            self.logger.info("check_success: Response device %s cmd %s cmd2 %s SUCCESS",
                             check_id, cmd1, cmd2)
            return True

        self.logger.info("check_success: No valid response found for device %s cmd %s cmd2 %s",
                         device_id, sent_cmd1, sent_cmd2)
        return False


    def clear_buffer(self):
        """Clear the hub buffer"""
        command_url = self.hub_url + '/1?XB=M=1'
        response = self.post_direct_command(command_url)
        self.logger.info("clear_buffer: %s", response)
        return response


   ## @TODO IN DEVELOPMENT
   ### TODO listen for linked page 35 http://cache.insteon.com/developer/2242-222dev-062013-en.pdf
   # link_type:
   #  00 as responder/slave
   #  01 as controller/master
   #  03 as controller with im initiates all linking or as responder when
   #     another device initiates all linking
   #  FF deletes the all link
    def start_all_linking(self, link_type, group_id):
        """Begin all linking"""
        self.logger.info("start_all_linking for type %s group %s",
                         link_type, group_id)
        self.direct_command_hub('0264' + link_type + group_id)
       # TODO: read response
        #    Byte Value Meaning
        #1 0x02 Echoed Start of IM Command
        #2 0x64 Echoed IM Command Number
        #3 <Code> Echoed <Code>
        #4 <ALL-Link Group> Echoed <ALL-Link Group>
        #5 <ACK/NAK> 0x06 (ACK) if the IM executed the Command correctly
        #0x15 (NAK) if an error occurred


    def cancel_all_linking(self):
        """Cancel all linking"""
        self.logger.info("cancel_all_linking")
        self.direct_command_hub('0265')
        ## TODO read response
            # 0x02 echoed start of command
            # 0x65 echoed im command
            # ack 06 or nak 15


    def group(self, group_id):
        """Create group object"""
        group_obj = Group(self, group_id)
        return group_obj


    def dimmer(self, device_id):
        """Create dimmer object"""
        dimmer_obj = Dimmer(self, device_id)
        return dimmer_obj


    def switch(self, device_id):
        """Create switch object"""
        switch_obj = Switch(self, device_id)
        return switch_obj


    def fan(self, device_id):
        """Create fan object"""
        fan_obj = Fan(self, device_id)
        return fan_obj
