#!/usr/bin/env python3

#########################################
###                                   ###
###       daaas_storage_boto3.py      ###
###       ~~~~~~~~~~~~~~~~~~~~~~      ###
###                                   ###
###   Import this from your notebook  ###
###   to easily access your storage   ###
###                                   ###
#########################################

####################
###      API     ###
####################
###
###  instances = get_instances()     # return available MinIO instances
###  s3 = Instances()                # return an object which has all the MinIO Clients as attributes
###
###  df    = pandas_from_json(r, *args, **kwargs)  # wrapper for pandas.read_json
###  table = arrow_from_json(r, *args, **kwargs)   # wrapper for pyarrow.json.read
###  df    = pandas_from_csv(r, *args, **kwargs)   # wrapper for pandas.read_csv
###  table = arrow_from_csv(r, *args, **kwargs)    # wrapper for pyarrow.read_csv
###
###  See: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-examples.html

import subprocess
import boto3
from os import remove
import os
import tempfile
import pandas as pd
import pyarrow as pa
from pyarrow import json
import sys

def get_minio_client(instance):
    """ Get the variables out of vault to create Minio Client. """

    d = {
        'MINIO_URL'        : None,
        'MINIO_ACCESS_KEY' : None,
        'MINIO_SECRET_KEY' : None
    }

    vault = f"/vault/secrets/{instance}"

    for var in d:
        CMD = f'echo $(source {vault}; echo ${var})'
        p = subprocess.Popen(CMD, stdout=subprocess.PIPE, shell=True,
                             executable='/bin/bash')
        d[var] = p.stdout.readlines()[0].strip().decode("utf-8")
    SECURE = d['MINIO_URL'].startswith('https')
    s3Client = boto3.client('s3',
                  endpoint_url=d['MINIO_URL'],
                  aws_access_key_id=d['MINIO_ACCESS_KEY'],
                  aws_secret_access_key=d['MINIO_SECRET_KEY'],
                  use_ssl=SECURE,
                  region_name="us-west-1")

    return s3Client

class Instances:
    clients = []

    def __init__(self):
        instance_list = get_instances()
        for i in instance_list:
            self.add_instance(i)  

    def add_instance(self, instance):
        self.clients.append(instance)
        # changes '-' to '_' in attribute name to create valid name
        setattr(self, instance.replace("-", "_"), get_minio_client(instance))  

def get_instances():
    instances = [file for file in os.listdir('/vault/secrets') if not file.endswith('.json')]
    return instances



def __from_s3__(table_type):
    def get_from_s3(r):
        """
        Read the response block by block as JSON,
        write to disk to keep memory from exploding.
        Then return a pandas/arrow dataframe of the object.
        """

        temp = tempfile.NamedTemporaryFile(delete=False)
        for event in r['Payload']:
            if 'Records' in event:
                temp.write(event['Records']['Payload'])
        temp.close()

        ### Choose how to interpret the JSON.
        ### With Arrow or Pandas?
        resp = table_type(temp.name)
        ###

        try:
            remove(temp.name)
        except:
            print(f"""
There was an error removing the file:
{temp.name}
... Proceeding anyway.
""", file=sys.stderr)

        return resp
    return get_from_s3


@__from_s3__
def pandas_from_json(r, *args, **kwargs):
    """ Read the stream from s3 and turn JSON into a pandas Dataframe. """
    kwargs['lines'] = True
    df = pd.read_json(r, *args, **kwargs)
    print("Created Dataframe with dimensions: (nrow, ncol) = %s" % str(df.shape), file=sys.stderr)
    return df

@__from_s3__
def arrow_from_json(r, *args, **kwargs):
    """ Read the stream from s3 and turn JSON into an Arrow Table. """
    table = json.read_json(r)
    print("Created Dataframe with dimensions: (nrow, ncol) = %s" % str(table.shape), file=sys.stderr)
    return table


@__from_s3__
def pandas_from_csv(r, *args, **kwargs):
    """ Read the stream from s3 and turn CSV into a pandas Dataframe. """
    kwargs['header'] = None
    df = pd.read_csv(r, *args, **kwargs)
    print("Created Dataframe with dimensions: (nrow, ncol) = %s" % str(df.shape), file=sys.stderr)
    return df

@__from_s3__
def arrow_from_csv(r, *args, **kwargs):
    """ Read the stream from s3 and turn CSV into an Arrow Table. """
    kwargs['header'] = None
    table = pa.read_csv(r, *args, **kwargs)
    print("Created Dataframe with dimensions: (nrow, ncol) = %s" % str(table.shape), file=sys.stderr)
    return table
