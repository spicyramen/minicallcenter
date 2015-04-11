# Ramen Labs 2014
# author:  Gonzalo Gasca Meza
# purpose: Handle incoming calls to Call Center
# MIT License

from flask import Flask, request, redirect
import twilio.twiml
from twilio.rest import TwilioRestClient
import os

app = Flask(__name__)

@app.route('/caller',methods=['POST'])
def caller():
	response = twilio.twiml.Response()
	response.enqueue("Main number queue", waitUrl="/wait")
	return str(response)

@app.route('/wait',methods=['POST'])
def wait():
	response = twilio.twiml.Response()
	response.say("Thanks for calling Ramen Networks. Your call is very important to us, one representative will be with you shortly")
	response.say("You are number %s in the queue" % request.form['QueuePosition'])
	client = TwilioRestClient("AC433e7b0bec93dc5996e4fb80b1e56eec","9cc9267fe09dab362d3be160f711a09d")
	response.play("http://demo.brooklynhacker.com/music/christmas.mp3")
	client.sms.messages.create(to="+14082186575",from_="+14157952944", body="Hey, someone is in the queue. Call to help")
	return str(response)

@app.route('/agent',methods=['POST'])
def agent():
	response = twilio.twiml.Response()
	with response.dial() as dial:
		dial.queue("Main number queue")
	return str(response)

if __name__ == "__main__":
	port = int(os.environ.get("PORT", 5000))
	app.debug = True
	app.run(host='0.0.0.0', port = port)
