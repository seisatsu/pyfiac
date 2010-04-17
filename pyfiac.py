#PyFiAC -- PYthon wiFI Auto Configurator
#Written by Michael D. Reiley ~ Omega Software Development Group @ OmegaDev.org

# * This program is free software. It comes without any warranty, to
# * the extent permitted by applicable law. You can redistribute it
# * and/or modify it under the terms of the Do What The Fuck You Want
# * To Public License, Version 2, as published by Sam Hocevar. See
# * http://sam.zoy.org/wtfpl/COPYING for more details.

import os, sys, string, time

global CONF
CONF = {'global_defaults':{}, 'network_defaults':{}, 'preset':{}, 'network':[]} #Initialize configuration value storage

def CheckRoot(): # Make sure that the user is root
	if (os.environ['USER'] != 'root'):
		return 'Error -1 : must be run as root'
	return 0

def cutout(inputstr, lind, rind): # Function to isolate a string -- Syntax: cutout(Input string to search through, anything on the left of the target string, anything on the right)
	if not inputstr == None:
		if len(lind) > 0:
			output = inputstr.partition(lind)[2] # Chop left boundary
		else:
			output = inputstr
		if len(rind) > 0:
			output = output.partition(rind)[0] # Chop right boundary
		if not output == None:
			return output
		else:
			return '-1'
	else:
		return '-1'

def ParseConfig(configfile): #Parse the configuration file
	if not os.path.isfile(configfile): # Make sure configuration file exists
		return 'Error -2 : unable to find config file'
	configfile = file(configfile, 'r')
	newsection = 0 # Some variables must be initialized
	global_category = ''
	category = ''
	conf_var = ''
	conf_value = ''
	print "Parsing conf file..."
	while 1:
		conf_line = configfile.readline()
		if conf_line == '': # End of file?
			break
		if conf_line == '\n': # Empty line?
			continue
		if '#' in conf_line: # Comment?
			conf_line = conf_line.split('#')
			conf_line = conf_line[0]
			if conf_line == '' or conf_line == '\n':
				continue
		
		conf_line = conf_line.replace('\t', '') # Strip whitespace
		conf_line = conf_line.replace('\n', '')

		if '=' in conf_line: # Fix to allow whitespace in ESSID
			conf_line = conf_line.split('=')
			conf_line[0] = conf_line[0].replace(' ', '')
			conf_line[1] = conf_line[1].lstrip()
			conf_line = conf_line[0] + '=' + conf_line[1]
			conf_line = conf_line.rstrip()
		
		if conf_line == '': # Garbage line
			continue
		if '[' in conf_line and ']' in conf_line:
			global_category = cutout(conf_line, '[', ']')
			newsection = 1
			if global_category == -1:
				return 'Error -4 : config file error (1)'
		if '.' in conf_line and '=' in conf_line:
			conf_line = conf_line.split('.', 1) # Isolate category
			category = conf_line[0]
			conf_line = conf_line[1]
			conf_line = conf_line.split('=', 1) # Isolate variable and value
			conf_var = conf_line[0]
			conf_value = conf_line[1]
		
		# Begin filling the CONF dictionary!
		
		if newsection == 1 and 'preset(' in global_category.lower(): # New preset
			preset_num = cutout(global_category, '(', ')')
			if preset_num == -1:
				return 'Error -4 : config file error'
			CONF['preset'][preset_num] = {}
		elif newsection == 0 and 'preset(' in global_category.lower(): # Add value to preset
			if not category in CONF['preset'][preset_num]:
				CONF['preset'][preset_num][category] = {}
			CONF['preset'][preset_num][category][conf_var] = conf_value
		elif global_category.lower() == 'defaults': # Set default values
			if category.lower() == 'global':
				CONF['global_defaults'][conf_var] = conf_value
			if category.lower() == 'network':
				CONF['network_defaults'][conf_var] = conf_value
		elif newsection == 1 and global_category.lower() == "network": # New network
			CONF['network'].append({})
		elif newsection == 0 and global_category.lower() == "network": # Add value to network
			CONF['network'][-1][conf_var] = conf_value
		else:
			return 'Error -4 : config file error (2)'
		
		newsection = 0
	print CONF
	return 0

def scan():
	print "Scanning..."
	os.system('killall dhcpcd 2>/dev/null') # Kill programs that might occupy the device
	os.system('killall wpa_supplicant 2>/dev/null')
	os.system('ifconfig ' + CONF['global_defaults']['wifidev'] + ' down') # Some devices need to be reset first
	os.system('ifconfig ' + CONF['global_defaults']['wifidev'] + ' up')
	ret = os.system('iwlist ' + CONF['global_defaults']['wifidev'] + ' scan > /tmp/pyfiac.iwlist.tmp') # Get a list of networks
	if not ret == 0:
		return 'Error -5 : external program error'
	tmpfile = open('/tmp/pyfiac.iwlist.tmp')
	tmpfile = tmpfile.read()
	FOUND = 0
	for essid in CONF['network']:
		ret = 0
		if FOUND == 0:
			if 'ESSID:\"' + essid['essid'] + '\"' in tmpfile: # Look for a configured network
				print 'Connecting to ' + essid['essid'] + '...'
				FOUND = 1
				if essid['encryption'] == 'none':
					ret = connect_none(essid)
				elif essid['encryption'] == 'wep':
					ret = connect_wep(essid)
				elif essid['encryption'] == 'wpa':
					ret = connect_wpa(essid)
				else:
					return 'Error -4 : config file error (3)'
			else:
				ret = 1
	return ret
	
def get_preset(ref, query): # Look for and return a preset value if it exists.
	if 'preset' in ref:
		preset_num = ref['preset']
		if 'network' in CONF['preset'][preset_num]:
			if query in CONF['preset'][preset_num]['network']:
				return CONF['preset'][preset_num]['network'][query]
	elif query in ref:
		return ref[query]
	else:
		return ''

def static_ip(ref): # Assign static IP
	if not os.system('dhcpcd -S ip_address=' + get_preset(ref, 'ip')
	+ ' -S routers=' + get_preset(ref, 'gateway')
	+ ' ' + CONF['global_defaults']['wifidev']) == 0:
		return 'Error -5 : external program error'
	return 0
	
def dhcp_ip(ref): # Assign DHCP IP
	if not os.system('dhcpcd ' + CONF['global_defaults']['wifidev']) == 0:
		return 'Error -5 : external program error'
	return 0

def connect_none(ref): # Connect to unencrypted access point
	ret = os.system('iwconfig ' + CONF['global_defaults']['wifidev'] + ' essid \'' + ref['essid'] + '\'')
	if not ret == 0:
		return 'Error -5 : external program error'
	val = get_preset(ref, 'connect')
	if val == 'static':
		return static_ip(ref)
	elif val == 'dhcp':
		return dhcp_ip(ref)
	else:
		return 'Error -4 : config file error (4)'

def connect_wep(ref): # Connect to WEP access point
	ret = os.system('iwconfig ' + CONF['global_defaults']['wifidev'] + ' essid \'' + ref['essid'] + '\' key ' + ref['key'])
	if not ret == 0:
		return 'Error -5 : external program error'
	val = get_preset(ref, 'connect')
	if val == 'static':
		return static_ip(ref)
	elif val == 'dhcp':
		return dhcp_ip(ref)
	else:
		return 'Error -4 : config file error (5)'

def connect_wpa(ref): # Connect to WPA access point
	os.system('wpa_passphrase \'' + ref['essid'] + '\' ' + ref['key'].replace('s:', '') + ' > /tmp/pyfiac.wpa_passphrase.tmp')
	tmpfile = open('/tmp/pyfiac.wpa_passphrase.tmp')
	tmpfile = tmpfile.read()
	key = cutout(tmpfile, 'psk=', '\n')
	wpaconf = open('/tmp/wpa_supplicant.conf', 'w') # Write WPA configuration
	wpaconf.write('ctrl_interface=/var/run/wpa_supplicant\n')
	wpaconf.write('ap_scan=1\n')
	wpaconf.write('network={\n')
	wpaconf.write('ssid=\"' + ref['essid'] + '\"\n')
	wpaconf.write('scan_ssid=0\n')
	wpaconf.write('proto=WPA RSN\n')
	wpaconf.write('key_mgmt=WPA-PSK\n')
	wpaconf.write('pairwise=CCMP TKIP\n')
	wpaconf.write('group=CCMP TKIP\n')
	wpaconf.write('psk=' + key + '\n')
	wpaconf.write('}\n')
	wpaconf.close()
	if not os.system('wpa_supplicant -B -D wext -i ' + CONF['global_defaults']['wifidev'] + ' -c /tmp/wpa_supplicant.conf') == 0: # Connect
		return 'Error -5 : external program error'
	val = get_preset(ref, 'connect')
	if val == 'static':
		return static_ip(ref)
	elif val == 'dhcp':
		return dhcp_ip(ref)
	else:
		return 'Error -4 : config file error (6)'

def main(): # Main loop
	ret = CheckRoot()
	if not ret == 0:
		print ret
		return ret
	if os.path.isfile('./pyfiac.conf'):
		ret = ParseConfig('./pyfiac.conf')
	elif os.path.isfile('~/.pyfiac.conf'):
		ret = ParseConfig('~/.pyfiac.conf')
	elif os.path.isfile('/etc/pyfiac.conf'):
		ret = ParseConfig('/etc/pyfiac.conf')
	if not ret == 0:
		print ret
		return ret
	while 1:
		ret = scan()
		if not ret == 0: # Scan failed
			if not ret == 1: # Error?
				print ret
				return ret
			time.sleep(10) # No error, scan again.
		else:
			break
	return 0

main()
