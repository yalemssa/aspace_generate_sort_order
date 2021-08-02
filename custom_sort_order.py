#!/usr/bin/python3

import csv
import json
import traceback
import requests
from concurrent.futures import ThreadPoolExecutor

#from rich.progress import track

'''
Gets a sort order/hierarchical position for each ArchivesSpace record in a spreadsheet.
'''

# def natsort(datasource):
# 	# this is only necessary if not inserting leading zeros
# 	return sorted(datasource, key=lambda v: [int(sequence_bit) for sequence_bit in sequence[2].split('.') if sequence_bit.isdigit()])

# def get_sort_order(ancestors, position):
# 	sort_order = ''
# 	for ancestor in ancestors:
# 		if ancestor.get('level') != 'collection':
# 			ancestor_position = str(ancestor.get('position')).zfill(5)
# 			sort_order = f"{sort_order}.{ancestor_position}"
# 	sort_order = f"{sort_order}.{str(position).zfill(5)}"
# 	return sort_order.lstrip('.')

def login(url=None, username=None, password=None):
    """Logs into the ArchivesSpace API"""
    try:
        if url is None and username is None and password is None:
            url = input('Please enter the ArchivesSpace API URL: ')
            username = input('Please enter your username: ')
            password = input('Please enter your password: ')
        auth = requests.post(url+'/users/'+username+'/login?password='+password).json()
        #if session object is returned then login was successful; if not it failed.
        if 'session' in auth:
            session = auth["session"]
            h = {'X-ArchivesSpace-Session':session, 'Content_Type': 'application/json'}
            print('Login successful!')
            return (url, h)
        else:
            print('Login failed! Check credentials and try again.')
            print(auth.get('error'))
            #try again
            u, heads = login()
            return u, heads
    except:
        print('Login failed! Check credentials and try again!')
        u, heads = login()
        return u, heads

def get_sort_order(ancestors, position, api_url, headers, sesh, uri):
	sort_order = ''
	for ancestor in ancestors:
		# don't want to include the collection, since resource records don't have a position
		if ancestor.get('level') != 'collection':
			record_json = sesh.get(f"{api_url}{ancestor.get('ref')}", headers=headers).json()
			record_position = str(record_json.get('position')).zfill(5)
			sort_order = f"{sort_order}.{record_position}"
	sort_order = f"{sort_order}.{str(position).zfill(5)}"
	return sort_order.lstrip('.')

def process_archival_objects(api_url, headers, sesh, row):
	try:
		# URI is in the fourth row in the report - could change this
		uri = row[3]
		record_json = sesh.get(f"{api_url}{uri}", headers=headers).json()
		# gets the position of the base ao
		position = record_json.get('position')
		# reverses ancestor array so it's ordered from collection on down to the lowest level ao
		ancestors = record_json.get('ancestors')[::-1]
		sort_order = get_sort_order(ancestors, position, api_url, headers, sesh, uri)
		# print(sort_order)
		row.append(sort_order)
		return row
	except Exception:
		print(traceback.format_exc())

def write_results(futures, csvoutfile):
	for future in futures:
		result = future.result()
		csvoutfile.writerow(result)

# def get_row_count(input_fp):
#   future progress bar - have to get it to work with concurrent.futures
# 	with open(input_fp) as infile:
# 		csvfile = csv.reader(infile)
# 		return len(list(csvfile))

def skip_report_rows(csvfile):
	first_row = next(csvfile)
	if first_row[0] == 'total_count':
		for i in range(2):
			next(csvfile)
		first_row = next(csvfile)
	return first_row

def main():
	config_file = json.load(open('config.json'))
	api_url, headers = login()
	input_fp = input('Enter path to input CSV: ')
	output_fp = f"{input_fp.replace('.csv', '')}_output.csv"
	#row_count = get_row_count(input_fp)
	try:
		with requests.Session() as sesh, ThreadPoolExecutor(max_workers=4) as pool, open(input_fp, 'r', encoding='utf8') as inputfile, open(output_fp, 'a', encoding='utf8') as outputfile:
			#, tqdm(total=row_count) as progbar
			futures = []
			csvfile = csv.reader(inputfile)
			header_row = skip_report_rows(csvfile)
			csvoutfile =  csv.writer(outputfile)
			csvoutfile.writerow(header_row + ['sort_order'])
			for row in csvfile:
				try:
					future = pool.submit(process_archival_objects, api_url, headers, sesh, row)
					#future.add_done_callback(lambda p: progbar.update())
					futures.append(future)
				except Exception:
					print(row)
					print(traceback.format_exc())
			if futures:
				write_results(futures, csvoutfile)
	except Exception:
		print(traceback.format_exc())


if __name__ == "__main__":
	main()
