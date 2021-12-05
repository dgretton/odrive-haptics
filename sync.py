#from .user import 90kv_intouch
import json
import requests

def syncData(deviceLocation):

	data = {"device":deviceLocation}

	r = requests.post(
		'https://hybihib2.glitch.me/',
		json=data
	)

	return(float(r.text))





