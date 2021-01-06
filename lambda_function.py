import urllib.robotparser, boto3, json, re, base64
s3=boto3.client('s3')


def lambda_handler(event, context):
    
    bucket=event['Records'][0]['s3']['bucket']['name']
    key=urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    try:
        response=s3.get_object(Bucket=bucket, Key=key)
        
        text=response["Body"].read().decode()
        
        content_length = len(text)
        pointer = 0
        payload=""
        
        while pointer < content_length:
            
            matchPos=re.search("\n", text[pointer:])
            
            if matchPos!=None:
                data=json.loads(text[pointer:matchPos.end()+pointer])
                base64_message = data['rawData']
                base64_bytes = base64_message.encode('utf-8')
                message_bytes = base64.b64decode(base64_bytes)
                message = message_bytes.decode('utf-8')
                payload=payload+message
                pointer=matchPos.end()+pointer
            else:
                pointer=content_length+1
        
        encoded_payload=payload.encode("utf-8")
        
        bucket_name = bucket
        file_name = key
        s3_path = "rawFailed/" + file_name
        
        print('writing to bucket:',bucket_name, ' s3_key:', s3_path)
        
        s3write = boto3.resource("s3")
        s3write.Bucket(bucket_name).put_object(Key=s3_path, Body=encoded_payload)        
        
        return 'Success!'
        
    except Exception as e:
        print(e)
        raise e
    
    
    
