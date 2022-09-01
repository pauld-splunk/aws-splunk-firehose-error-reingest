import base64, json, gzip, boto3, io, time

def transfm_log_ev(log_ev):
    return log_ev['message'] + '\n'

def process_recs(recs):
    p_size = len(recs)*128
    size_met = False
    for r in recs:
        data = base64.b64decode(r['data'])
        str_io_data = io.BytesIO(data)
        with gzip.GzipFile(fileobj=str_io_data, mode='r') as f:
            data = json.loads(f.read())

        rec_id = r['recordId']
        if data['messageType'] == 'CONTROL_MESSAGE':
            yield {'result': 'Dropped','recordId': rec_id}
        elif data['messageType'] == 'DATA_MESSAGE':
            if size_met:
                yield {'result':'Ok','recordId':rec_id}
            else:
                data = ''.join([transfm_log_ev(e) for e in data['logEvents']])
                data = base64.b64encode(data.encode('utf-8')).decode()
                if (p_size+len(data)+len(rec_id)) > 6000000:
                    size_met = True
                    yield {'result':'Ok','recordId':rec_id}
                else:
                    p_size += len(data)+len(rec_id)
                    yield {'data': data,'result': 'Ok','recordId': rec_id}
        else:
            yield {'result': 'ProcessingFailed','recordId': rec_id}

def put_recs_to_fh(strm, recs, client, attempts):
    f_recs = []
    codes = []
    err_msg = ''

    resp = None
    try:
        resp = client.put_record_batch(DeliveryStreamName=strm, Records=recs)
    except Exception as e:
        f_recs = recs
        err_msg = str(e)

    if not f_recs and resp and resp['FailedPutCount'] > 0:
        for idx, res in enumerate(resp['RequestResponses']):
            if 'ErrorCode' not in res or not res['ErrorCode']:
                continue

            codes.append(res['ErrorCode'])
            f_recs.append(recs[idx])

        err_msg = 'Err codes: ' + ','.join(codes)

    if len(f_recs) > 0:
        if attempts + 1 < 5:
            print('Retrying after putRecBatch fail. %s' % (err_msg))
            time.sleep(1)
            put_recs_to_fh(strm, f_recs, client, attempts + 1)
        else:
            raise RuntimeError('Failed ingest after 5 attempts. %s' % err_msg)


def handler(event, ctxt):
    recs_in_req = len(event['records'])

    recs = list(process_recs(event['records']))
    data_by_rec_id = {rec['recordId']: {'data': base64.b64decode(rec['data'])} for rec in event['records']}
    put_rec_batches = []
    recs_to_reing = []
    recs_to_reing_size = 0
    total_recs_to_reing = 0

    for idx, rec in enumerate(recs):
        if rec['result'] != 'Ok':
            continue

        if 'data' not in rec:
            total_recs_to_reing += 1
            rec_to_reingest = {'Data': data_by_rec_id[rec['recordId']]['data']}

            if len(recs_to_reing) >= 500 or (recs_to_reing_size + len(rec_to_reingest['Data'])) > 4000000:
                put_rec_batches.append(recs_to_reing)
                recs_to_reing = []
                recs_to_reing_size = 0

            recs_to_reing.append(rec_to_reingest)
            recs_to_reing_size += len(rec_to_reingest['Data'])
            recs[idx]['result'] = 'Dropped'

    if len(recs_to_reing) > 0:
        put_rec_batches.append(recs_to_reing)

    recs_reingstd = 0
    if len(put_rec_batches) > 0:
        client = boto3.client('firehose', event['deliveryStreamArn'].split(':')[3])
        for recBatch in put_rec_batches:
            put_recs_to_fh(event['deliveryStreamArn'].split('/')[1], recBatch, client, 0)
            recs_reingstd += len(recBatch)
            print('Reingested %d/%d recs out of %d Recs Recvd' % (
                recs_reingstd, total_recs_to_reing, recs_in_req))

        print('Recs reingsted: ' + str(recs_reingstd))

    print('Recs recvd: ' + str(recs_in_req) + ' Recs processed: ' + str(recs_in_req - recs_reingstd))

    return {'records': recs}