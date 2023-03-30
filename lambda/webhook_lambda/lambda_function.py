import logging
import boto3
import requests
import json

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

def lambda_handler(event, context):
    # Get input from Step Function
    # s3_bucket = event['s3_bucket']
    # s3_key = event['s3_key']
    workdocs_folder_id = '8482e2b73304f3b194d7779fe195b33813b0997fd41859837601900aa71d50b8'

    # Initialize S3 and WorkDocs clients
    s3 = boto3.client('s3')
    wd = boto3.client('workdocs')

    # Read HTML file from S3
    webhook_payload = json.loads(event['body'])
    order_id = webhook_payload['id']
    file_name = f'order-{order_id}.html'
    # ... retrieve any other necessary order data ...

    # Create an EventBridge event and publish it to the default event bus
    eventbridge = boto3.client('events')
    eventbridge.put_events(
        Entries=[
            {
                'Source': 'woocommerce.orders',
                'DetailType': 'order.created',
                'Detail': json.dumps(webhook_payload),
                'EventBusName': 'default'
            }
        ]
    )

    # Log event
    logger.info(f"Received event: {webhook_payload}")

    order_data = webhook_payload

    html = f"""
            <html>
            <head>
                <title>Order Receipt</title>
            </head>
            <body>
                <h1>Order Receipt</h1>
                <p><strong>Order ID:</strong> {order_data['id']}</p>
                <p><strong>Customer Name:</strong> {order_data['billing']['first_name']} {order_data['billing']['last_name']}</p>
                <p><strong>Customer Email:</strong> {order_data['billing']['email']}</p>
                <p><strong>Order Total:</strong> {order_data['total']}</p>
            </body>
            </html>
        """

    response = wd.initiate_document_version_upload(
        Name=file_name,
        ContentType="text/html",
        ParentFolderId=workdocs_folder_id
    )
    document_id = response['Metadata']['Id']
    version_id_latest = response['Metadata']['LatestVersionMetadata']['Id']
    url = response['UploadMetadata']['UploadUrl']
    # Upload HTML file to WorkDocs
    headers = response['UploadMetadata']['SignedHeaders']

    response = requests.put(url, headers=headers, data=html.encode('utf-8'))

    response = wd.update_document_version(
        DocumentId=document_id,
        VersionId=version_id_latest,
        VersionStatus='ACTIVE'
    )

    # Log document ID
    logger.info(f"Document ID: {document_id}")

    # Return the document ID as output
    return {
        'statusCode': 200,
        'body': json.dumps({'document_id': document_id})
    }
