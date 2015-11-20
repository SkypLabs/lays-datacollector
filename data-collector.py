#!/usr/bin/python3

import pika
import drest
import json
from os import getenv
from time import sleep
from sys import exit, stdout, stderr

lays_debug = getenv('LAYS_DEBUG')

if lays_debug == 'true':
	debug = True
else:
	debug = False

if debug:
	webapp_host = getenv('WEBSERVER_PORT_8000_TCP_ADDR', 'localhost')
	webapp_port = 8000
else:
	webapp_host = getenv('WEBSERVER_PORT_80_TCP_ADDR', 'localhost')
	webapp_port = 80

amqp_host = getenv('AMQPSERVER_PORT_5672_TCP_ADDR', 'localhost')
amqp_port = 5672

stdout.write('[*] Connection to AMQP server ({0}) ...\n'.format(amqp_host))

while True:
	try:
		amqp = pika.BlockingConnection(pika.ConnectionParameters(
			amqp_host,
			amqp_port
		))
		rd_channel = amqp.channel()
		rd_channel.queue_declare(queue='resources-discovery', durable=True)
		dc_channel = amqp.channel()
		dc_channel.queue_declare(queue='data-collector', durable=True)
		break
	except pika.exceptions.ConnectionClosed:
		stderr.write('[x] Failed !\n')
		stderr.write('[!] Retry in 3 seconds\n')
		sleep(3)
	except KeyboardInterrupt:
		stdout.write('[*] Aborded\n')
		exit(0)

stdout.write('[*] Connected !\n')
stdout.write('[*] Connection to WebApp API ({0}) ...\n'.format(webapp_host))

try:
	api = drest.api.TastyPieAPI('http://{0}:{1}/api/v1/'.format(webapp_host, webapp_port))
	api.auth('admin', '')
except (drest.exc.dRestAPIError, drest.exc.dRestRequestError) as e:
	stderr.write('[x] Failed ! : {0}\n'.format(e))
	amqp.close()
	exit(1)

stdout.write('[*] Connected !\n')

def resources_discovery(ch, method, properties, body):
	message = json.loads(body.decode())

	try:
		uuid = message['uuid']
		stdout.write('[*] New resource(s) from {0} :\n'.format(uuid))

		for resource in message['resources']:
			address = resource['address']
			mode = resource['mode']
			type = resource['type']
			dimension = resource['dimension']

			stdout.write('\t - {0} : {1};{2};{3}\n'.format(address, mode, type, dimension))

			device = api.device.get(params=dict(uuid=uuid))

			# If device does not exist
			if device.data['meta']['total_count'] == 0:
				device_data = {
					'uuid' : uuid,
				}

				api.device.post(device_data)

			device_id = api.device.get(params=dict(uuid=uuid)).data['objects'][0]['id']

			# If resource does not exist
			if api.resource.get(params=dict(device__uuid=uuid, address=address)).data['meta']['total_count'] == 0:
				resource_data = {
					'address' : address,
					'device' : '/api/v1/device/{0}/'.format(device_id),
					'mode' : mode,
					'type' : type,
					'dimension' : dimension,
				}

				api.resource.post(resource_data)
	except KeyError as e:
		stderr.write('[x] Bad request : unknown key {0}\n\t=> {1}\n'.format(e, message))
	except drest.exc.dRestRequestError as e:
		stderr.write('[x] REST error : {0}\n'.format(e))
		return

	ch.basic_ack(delivery_tag = method.delivery_tag)

def data_collector(ch, method, properties, body):
	message = json.loads(body.decode())

	try:
		stdout.write('[*] New data from {0} :\n'.format(message['uuid']))

		for data in message['data']:
			address = resource['address']
			value = resource['value']

			stdout.write('\t - {0} : {1}\n'.format(address, value))
	except KeyError:
		stderr.write('[x] Bad request :\n\t=> {0}\n'.format(message))

	ch.basic_ack(delivery_tag = method.delivery_tag)

rd_channel.basic_consume(
	resources_discovery,
	queue='resources-discovery',
)

dc_channel.basic_consume(
	data_collector,
	queue='data-collector',
)

stdout.write('[*] Waiting for data ...\n')

try:
	rd_channel.start_consuming()
	dc_channel.start_consuming()
except KeyboardInterrupt:
	amqp.close()
	stdout.write('[*] Bye !\n')
