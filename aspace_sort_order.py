#!/usr/bin/python3

import csv
import json
import os
import sys
import traceback
import requests
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    TextColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    Progress,
    TaskID,
)

#from tqdm import tqdm

'''
Gets a sort order/hierarchical position for each ArchivesSpace record in a spreadsheet.
'''


def login(url=None, username=None, password=None):
    """Logs into the ArchivesSpace API"""
    try:
        if (url in (None, '')) or (username in (None, '')) or (password in (None, '')):
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

def process_archival_objects(api_url, headers, sesh, row, progbar, master_task):
    try:
        progbar.advance(master_task, 1)
        # URI is in the fourth row in the report - could change this?
        uri = row[3]
        record_json = sesh.get(f"{api_url}{uri}", headers=headers).json()
        # gets the position of the base ao
        position = record_json.get('position')
        # reverses ancestor array so it's ordered from collection on down to the lowest level ao
        ancestors = record_json.get('ancestors')[::-1]
        sort_order = get_sort_order(ancestors, position, api_url, headers, sesh, uri)
        # print(sort_order)
        row.insert(0, sort_order)
        return row
    except Exception:
        print(traceback.format_exc())

def write_results(futures, csvoutfile):
    for future in futures:
        result = future.result()
        csvoutfile.writerow(result)

def skip_report_rows(csvfile):
    first_row = next(csvfile)
    if first_row[0] == 'total_count':
        for i in range(2):
            next(csvfile)
        first_row = next(csvfile)
    return first_row

def get_rowcount(fp):
    with open(fp) as csvin:
        return len(list(csv.reader(csvin))) - 4


def rich_setup():
    console = Console(record=True)
    progress = Progress(
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        "[progress.completed]{task.completed}/{task.total}",
        "•",    
        TimeRemainingColumn(),
        console=console
    )
    return progress

def main():
    EXE_PATH = os.getcwd()
    #EXE_PATH = sys.executable.replace('/aspace_sort_order', '')
    progbar = rich_setup()
    cfg = json.load(open(f"{EXE_PATH}/config.json"))
    api_url, headers = login(url=cfg.get('aspace_api_url'), username=cfg.get('aspace_username'), password=cfg.get('aspace_password'))
    if cfg.get('input_csv') in (None, ''):
        input_fp = input('Enter path to input CSV: ')
    else:
        input_fp = cfg.get('input_csv')
    output_fp = f"{input_fp.replace('.csv', '')}_output.csv"
    rowcount = get_rowcount(input_fp)
    master_task = progbar.add_task("overall", total=rowcount, filename="Overall Progress")
    try:
        with progbar, requests.Session() as sesh, ThreadPoolExecutor(max_workers=4) as pool, open(input_fp, 'r', encoding='utf8') as inputfile, open(output_fp, 'a', encoding='utf8') as outputfile:
            futures = []
            csvfile = csv.reader(inputfile)
            header_row = skip_report_rows(csvfile)
            csvoutfile =  csv.writer(outputfile)
            csvoutfile.writerow(['sort_order'] + header_row)
            for row in csvfile:
                try:
                    future = pool.submit(process_archival_objects, api_url, headers, sesh, row, progbar, master_task)
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
