import json
import boto3
import requests
from typing import NamedTuple
from urllib.parse import unquote
from contentful_management import Client
import os
from time import sleep
from algoliasearch import algoliasearch


class S3UploadEvent(NamedTuple):
    key: str
    bucket: str

    @classmethod
    def from_json(cls, source: dict):
        return S3UploadEvent(
            bucket=source['s3']['bucket']['name'],
            key=unquote(source['s3']['object']['key'])
        )

    def to_object_uri(self):
        return f"s3://{self.bucket}/{self.key}"


class AssetCreateEvent(NamedTuple):
    asset_id: str
    environment_id: str
    space_id: str

    @classmethod
    def from_json(cls, source: dict):
        return AssetCreateEvent(
            space_id=source['sys']['space']['sys']['id'],
            environment_id=source['sys']['environment']['sys']['id'],
            asset_id=source['sys']['id']
        )

    def url(self):
        return f"https://api.contentful.com/spaces/{self.space_id}/environments/{self.environment_id}/assets/{self.asset_id}"


def get_asset_url(js):
    f = js['fields'].get('file', None)
    
    if f:
        return f['en-US']['url']
    else:
        print(js)
        return None
    

def recognize_s3_object(event: S3UploadEvent) -> dict:
    client = boto3.client('rekognition')
    print(f"Starting recognition for object '{s3_event.to_object_uri()}'")
    response = client.detect_labels(
        Image={
                'S3Object': {
                'Bucket': s3_event.bucket,
                'Name': s3_event.key
            }
        },
        MaxLabels=10,
        MinConfidence=0,
    )

    return response


def recognize_binary(bin_content) -> dict:
    client = boto3.client('rekognition')
    response = client.detect_labels(
        Image={
            'Bytes': bin_content,
        },
        MaxLabels=20,
        MinConfidence=70.0,
    )

    return response


def poll_asset_url(asset_event: AssetCreateEvent, wait_seconds=3, max_retries=20) -> str:
    asset_url = None
    client = Client(os.environ['CMA_TOKEN'])

    for i in range(max_retries):
        print(f"Retrieving asset url: attempt {i}")
        asset = client.assets(asset_event.space_id, asset_event.environment_id).find(asset_event.asset_id)
        asset_url = asset.url()
        if asset_url:
            return f"http:{asset_url}"

        print(f"No asset url available on attempt {i}")
        sleep(wait_seconds)
        
    raise Exception("Could not get asset url")


def index_asset(index, asset_id, space_id, asset_url, labels):
    to_index = {
        'objectID': ''.join([space_id, asset_id]),
        'space_id': space_id,
        'Labels': labels['Labels'],
        'url': asset_url,
        'asset_id': asset_id,
        'thumb_url': asset_url + "?w=100"
    }

    index.add_object(to_index)


def all_assets(space_id: str, environment_id: str):
    assets = []

    def get_page(start: int):
        resp = requests.get(
            f"https://api.contentful.com/spaces/{space_id}/environments/{environment_id}/assets?skip={start}&access_token={os.environ['CMA_TOKEN']}"
        )

        data = resp.json()
        next_start = start + 100
        total = data.get('total')

        for item in data.get('items'):
            assets.append(
                item
            )

        if next_start < total:
            get_page(next_start)

    get_page(0)
    return assets


def reindex_all(space_id, environment_id):
    al_client = algoliasearch.Client(os.environ['ALGOLIA_APP'], os.environ['ALGOLIA_KEY'])
    # al_client.delete_index('art-assets')
    client = Client(os.environ['CMA_TOKEN'])
    assets = all_assets(space_id, environment_id)
    index = al_client.init_index('art-assets')
    index.set_settings({
        'minWordSizefor1Typo': 5,
        'minWordSizefor2Typos': 10,
        })

    for asset in assets:
        asset_id = asset['sys']['id']
        asset_url = get_asset_url(asset)

        print(asset_id)
        print(asset_url)

        next
        if not asset_url:
            print(f"Asset has no url, skipping: {asset}")
            continue

        url = f"https:{asset_url}"
        response = requests.get(url)
        
        if int(response.headers.get('Content-Length')) > 5242880:
            print(f"Asset to large for rekognition: {asset}")
            continue

        labels = recognize_binary(response.content)

        index_asset(
            index, asset_id, space_id, url, labels,
        )

        print(f"Indexed asset metadata for asset id {asset_id}")


def lambda_handler(event, context):
    try:
        asset_event = AssetCreateEvent.from_json(event)
        response = requests.get(asset_event.url())
        print(response)

        print("lambda_handler")

        url = poll_asset_url(asset_event)
        print(url)
        
        response = requests.get(url)
        print(response)

        labels = recognize_binary(response.content)
        print(labels)

        al_client = algoliasearch.Client(os.environ['ALGOLIA_APP'], os.environ['ALGOLIA_KEY'])
        index = al_client.init_index('art-assets')

        print(index, asset_event.asset_id, asset_event.space_id, url, labels)

        index_asset(
            index, asset_event.asset_id, asset_event.space_id, url, labels,
        )

    except Exception as e:
        print(f"Failed to handle event {event}: {e}")
        
        raise e


def delete_objects():
    objects = ['qc6kbklzr3ku7ylT9Df729RAvqZFaMsfhR']

    al_client = algoliasearch.Client(os.environ['ALGOLIA_APP'], os.environ['ALGOLIA_KEY'])
    index = al_client.init_index('art-assets')
    index.delete_objects(objects)
