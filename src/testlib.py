import requests
import hashlib, hmac, sys

###############################################################################

SALT_SYSTEM = "mk3ScGbRwl6eW1DpbsmyFe6kzpdQBV2WTtfHzncJwmlLRIJCtbVIGdLyT6pW7zuz"

if len(sys.argv) <= 1 or sys.argv[1] == "localhost":
	SERVER = "localhost/pvforecast"
elif sys.argv[1] == "server":
	SERVER = "www.pvforecast.cz"
else:
	SERVER = "unknown"


print ("##################################")
print ("# Server: {} ".format(SERVER))
print ("##################################")

###############################################################################

def http(url, data):
	postdata = {
		"data": data
	}
	return requests.post(url, data=postdata).text

def sha256(message):
	m = hashlib.sha256()
	m.update(message)
	return m.hexdigest()

def hmac_sha256(message, key):
	messageBytes = bytes(message).encode('utf-8')
	keyBytes = bytes(key).encode('utf-8')

	return hmac.new(keyBytes, messageBytes, digestmod=hashlib.sha256).hexdigest()