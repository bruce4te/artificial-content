import json
import boto3
import requests
from typing import NamedTuple
from urllib.parse import unquote
from contentful_management import Client
import os
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
        MaxLabels=10,
        MinConfidence=0,
    )

    return response


def lambda_handler(event, context):
    try:
        asset_event = AssetCreateEvent.from_json(event)
        response = requests.get(asset_event.url())
        print(response)

        client = Client(os.environ['CMA_TOKEN'])

        asset = client.assets(asset_event.space_id, asset_event.environment_id).find(asset_event.asset_id)
        url = asset.url()
        print(url)
        
        response = requests.get(f"http:{asset.url()}")
        print(response)

        labels = recognize_binary(response.content)
        print(labels)

        al_client = algoliasearch.Client(os.environ['ALGOLIA_APP'], os.environ['ALGOLIA_KEY'])
        index = al_client.init_index('art-assets')
        index.add_object(labels)

    except Exception as e:
        print(f"Failed to handle event {event}: {e}")
        
        raise e
