#!/usr/bin/env python3

import os
import sys
sys.path.insert(0, '/nethome/'+os.getlogin()+'/test/testq/rsmas_insar/3rdparty/accounts/SSARA')
import time
import subprocess
import logging
import datetime  
import password_config as password

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

std_formatter = logging.Formatter("%(levelname)s - %(message)s")

fileHandler = logging.FileHandler(os.getenv('OPERATIONS')+'/LOGS/ssara_rsmas.log', 'a+', encoding=None)
fileHandler.setLevel(logging.INFO)
fileHandler.setFormatter(std_formatter)

streamHandler = logging.StreamHandler()
streamHandler.setLevel(logging.INFO)
streamHandler.setFormatter(std_formatter)

logger.addHandler(fileHandler)
logger.addHandler(streamHandler)

"""
    Checks if the files too be downloaded actually exist or not on the system as a means of validating whether
    or not the wrapper completed succesdully.

    Parameters: run_number: int, the current iteration the wrapper is on (maxiumum 10 before quitting)
    Returns: none

"""
def check_downloads(run_number, args):
	ssara_output = subprocess.check_output(['ssara_federated_query-cj.py']+args[1:len(args)]+["--print"])
	ssara_output_array = ssara_output.decode('utf-8').split('\n')
	ssara_output_filtered = ssara_output_array[5:len(ssara_output_array)-1]

	files_to_check = []
	for entry in ssara_output_filtered:
		files_to_check.append(entry.split(',')[-1].split('/')[-1])


	for f in files_to_check:
		if not os.path.isfile(str(os.getcwd())+"/"+str(f)):
			logger.warning("The file, %s, didn't download correctly. Running ssara again.", f)
			run_ssara(run_number+1, serial=True)
			return
	print("Everything is there!")

"""
     Runs ssara_federated_query-cj.py and checks continuously for whether the data download has hung without comleting
     or exited with an error code. If either of the above occur, the function is run again, for a maxiumum of 10 times.
         
     Parameters: run_number: int, the current iteration the wrapper is on (maxiumum 10 before quitting)
     Returns: none

"""	
def run_ssara(run_number=1, serial=False):

	logger.info("RUN NUMBER: %s", str(run_number))	
	if not serial and run_number > 10:
		return 0	
	
	with open(sys.argv[1], 'r') as template_file:
		options = ''
		for line in template_file:
			if 'ssaraopt' in line:
				options = line.strip('\n').rstrip().split("= ")[1]
				break;
					
	# Compute SSARA options to use
	options = options.split(' ')
	
	if serial and run_number > 2:
		return 0
	
	if serial:
		filecsv_options = ['ssara_federated_query.py']+options+['--print', '|', 'awk', "'BEGIN{FS=\",\"; ORS=\",\"}{ print $14}'", '>', 'files.csv']
		csv_command = ' '.join(filecsv_options)
		filescsv_status = subprocess.Popen(csv_command, shell=True).wait()
		sed_command = "sed 's/^.\{5\}//' files.csv > new_files.csv";
		subprocess.Popen(sed_command, shell=True).wait()
		serial_status = subprocess.Popen(['download_ASF_serial.py', '-username', password.asfuser, '-password', password.asfpass, 'new_files.csv']).wait()
		if serial_status is not 0:
			return 1
		else:
			run_ssara(run_number+1, serial=serial)


	ssara_options = ['ssara_federated_query.py'] + options + ['--parallel', '10', '--print', '--download']	

	ssara_process = subprocess.Popen(ssara_options)
		
	completion_status = ssara_process.poll()
	hang_status = False
	wait_time = 10	# wait time in `minutes` to determine hang status
	
	prev_size = -1
	
	i=0
	while completion_status is None:
		
		i=i+1
		curr_size = int(subprocess.check_output(['du','-s', os.getcwd()]).split()[0].decode('utf-8'))

		if prev_size == curr_size:
			hang_status = True
			logger.warning("SSARA Hung")
			ssara_process.terminate()
			break;
		
		time.sleep(60*wait_time)
		prev_size = curr_size
		completion_status = ssara_process.poll()
		logger.info("{} minutes: {:.1f}GB, completion_status {}".format(i*wait_time, curr_size/1024/1024, completion_status))
			
	exit_code = completion_status
	logger.info("EXIT CODE: %s", str(exit_code))
	
	bad_codes = [137]
	
	if exit_code in bad_codes or hang_status:
		logger.warning("Something went wrong, running again")
		run_ssara(run_number=run_number+1, serial=serial)

	#check_downloads(run_number, sys.argv)
	return 1


if __name__ == "__main__":
	logger.info("DATASET: %s", str(sys.argv[1].split('/')[-1].split(".")[0]))
	logger.info("DATE: %s", datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"))
	succesful = run_ssara(serial=True)
	logger.info("SUCCESS: %s", str(succesful))
	logger.info("------------------------------------")					
