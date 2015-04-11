__author__ = 'gogasca'

from flask import Flask, request, redirect, abort, jsonify, make_response
from twilio.rest import TwilioRestClient
import twilio.twiml
import ConfigParser, logging, ast, re, os, sys, inspect

dialer = Flask(__name__)
# Start app from Heroku using web: 1 python bin/app.py
config = ConfigParser.ConfigParser()
config.read("config.ini")

# TODO Connection to retrieve caller information from DB
activeCalls = []
callers = {"+14082186575": "Gonzalo Gasca Meza",
		   "+14158571747":"Gonzalo Gasca Meza",
		   "+14088248487": "Vanessa Yeoh",
		   "+525557969469":"Papa Mama o anexados",
		   "+525557996297":"Papa Mama o anexados"}

# API definition
"""
    Ramen Labs - API v0.1
    ----------------------------------------------------------------------------------------------------

    dial:       Initiates dialing to customer
                Params: (destination, date, persona, organization)

                    destination:    E.164/SIP URI
                    date:           'now' | date RFC 2822 - Fri, 20 Aug 2010 01:13:42 +0000
                    persona:        Class persona
                    organization:   string
                    agent:          Agent information
                                        name:
                                        destination:
                                        altDestination1:
                                        altDestination2:
                                        altDestination3:
                                        altDestination4:
                                        altDestination5:
                                        
                    fallback:       Number to use when agent is not responding

    connect:    Connect customer call to selected agent
                Params: (Class <agent>, agent telephone number, customer telephone number)

                    agent: Class agent
                    agent telephone number: E.164/SIP URI
                    customer telephone number:  E.164/SIP URI

    transfer:   Transfer agent to customer
                Params: (customer telephone number)


    wait:       Play music to customer and notify selects agent
                Params:

    acd:        Handles calls to main queue

    agent:      Agent handle from main queue

    callstatus: Verifies call status
                Params: (CallId)

"""
########################################################################################################################

class Agent():
    def __init__(self,agentId):
        logging.info('New agent is created callId: ' + agentId)

class Customer():
     def __init__(self,customerId):
        logging.info('New customer is created callId: ' + customerId)

class Call():
    def __init__(self,callId):
        logging.info('New call is created callId: ' + callId)

class CDR():
    def __init__(self):
        self.id = '0'
    def create(self, account, callSid, callingNumber, calledNumber, duration, status):
        self.account = account
        self.callSid = callSid
        self.callingNumber = callingNumber
        self.calledNumber = calledNumber
        self.duration = duration
        self.status = status

    def insert(self):
        print 'Insert record'


########################################################################################################################

#Recieves dial request from Notifier Layer
@dialer.route("/api/dial", methods=['GET', 'POST'])
def dial():
    method = 'dial'
    logging.info(
        "------------------------------------------------------Dial Request------------------------------------------------------")
    try:
        # Obtain parameters: destination,schedule,persona,organization

        destination = request.values.get('destination', None)   #Mandatory
        schedule = request.values.get('date', None)
        persona = request.values.get('persona', None)
        organization = request.values.get('organization', None)

        #Recieves dial request from Notifier Layer
        if validate_api_request(method,str(destination),0) == 0:
            logging.info('destination: ' + destination)

            if validate_api_request(method,str(schedule),1) == 0:
                logging.info('date: ' + schedule)
                #Find available agent, and transfer customer to it.
                locate_agent(destination)
                return make_response(jsonify({'Dial': 'Success'}), 200)
            else:
                logging.error('Invalid schedule in dial request: ' + str(schedule))
                return errorRequest(method, 102, 400)
        else:
            logging.error('Invalid destination in dial request: ' + str(destination))
            return errorRequest(method, 103, 400)

        #TODO validate persona
        #TODO validate organization
        #TODO create database schema for relevant customer information

    except Exception, e:
        logging.error("Exception found " + str(e))



#Connects caller to Main Queue
@dialer.route("/api/connect", methods=['GET', 'POST'])
def connect(agent, agentTelephoneNumber, destination):
    method = 'connect'
    logging.info(
        "------------------------------------------------------Call Customer------------------------------------------------------")
    #Reading logFile location
    account_sid = config.get('Twilio', 'account_sid')
    auth_token = config.get('Twilio', 'auth_token')
    twilioTelephoneNumber = config.get('Twilio', 'telephoneNumber')

    try:
        #Create new instance of TwilioRestCLient
        logging.info('(connect) Connecting agent: ' + agentTelephoneNumber)
        client = TwilioRestClient(account_sid, auth_token)
        call = client.calls.create(to=agentTelephoneNumber,         # agent's telephone Number
                                   from_=twilioTelephoneNumber,     # Must be a valid Twilio number
                                   url= config.get('System', 'url') + '/api/transfer'  + '?Destination=' + destination,
                                   status_callback= config.get('System', 'url') + '/api/callstatus' + '?CallType=1',
                                   status_callback_method='POST',
                                   if_machine='Continue',
                                   caller=twilioTelephoneNumber,
                                   timeout=int(config.get('Twilio', 'answerTooLate')))
    except Exception, e:
        logging.error('Exception found call connect' + str(e))


#Transfer agent to customer
@dialer.route('/api/transfer', methods=['POST'])
def transfer():
    method = 'transfer'
    logging.info(
        "------------------------------------------------------Call Transfer------------------------------------------------------")

    callId = request.values.get('CallSid', None)
    status = request.values.get('CallStatus', None)
    entity = request.values.get('AnsweredBy', None)
    agentNumber = request.values.get('Called', None)
    destination = request.values.get('Destination', None)

    #Insert call into activeCall List
    logging.info('(transfer) Inserting callId: ' + callId)
    activeCalls.append(Customer(callId))

    # Twilio Response Object
    response = twilio.twiml.Response()
    if entity == 'machine':
        logging.warn('(transfer) Call was not answered by agent: ' + agentNumber  + '. Agent is unavailable. Call was answered by a machine. Call Id: ' + callId)
        #response.say('Agent is unavailable')
    elif entity == 'human':
        logging.info('(transfer) Call answered by available agent: ' + agentNumber )
        response.say('Customer will be connected...')
        logging.info('(transfer) Calling customer: ' + str(destination) + ' CallId: ' + callId)
        # Dial to customer...
        response.dial(number=destination,
                      action= config.get('System', 'url') + '/api/callstatus' + '?CallType=2',
                      method='POST',
                      timeLimit=int(config.get('Twilio', 'maxDuration')),
                      timeout=int(config.get('Twilio', 'answerTooLate')))
    else:
        logging.warn('Call not answered...status: ' + status)

    return str(response)


#After sending call to agent log cdr information
@dialer.route('/api/callstatus', methods=['POST'])
def callstatus():
    method = 'callstatus'
    logging.info(
        "------------------------------------------------------Call Status------------------------------------------------------")

    try:
        # Twilio Response Object
        response = twilio.twiml.Response()

        account_sid = config.get('Twilio', 'account_sid')
        auth_token = config.get('Twilio', 'auth_token')

        account = request.values.get(account_sid, None)


        callSid = request.values.get('CallSid', None)
        status = request.values.get('CallStatus', None)
        callingNumber = request.values.get('From', None)
        calledNumber = request.values.get('Called', None)
        duration = request.values.get('CallDuration', None)
        entity = request.values.get('AnsweredBy', None)
        callType = request.values.get('CallType', None)


        if callType=='1':
            logging.info('(callstatus) call ' + callSid + ' to agent.')
        elif callType=='2':
            logging.info('(callstatus) call ' + callSid + ' to customer.')
            status = request.values.get('DialCallStatus', None)
            DialCallSid = request.values.get('DialCallSid', None)
            client = TwilioRestClient(account_sid, auth_token)
            call = client.calls.get(DialCallSid)
            calledNumber = call.to
        else:
            logging.warn('(callstatus) call ' + callSid + ' unknown')

        logging.info('(callstatus) call status received. Called: ' + calledNumber + ' ' + ' Status: ' + str(status))

        if entity == 'machine':
            if status == 'completed':
                logging.warn('(callstatus) Machine answered. Call: ' + callSid + '. Status: ' + str(status))
                # TODO Create CDR
                generate_cdr(callType)
            else:
                logging.warn('(callstatus) call: ' + callSid + ' to ' + calledNumber + ' Status: ' + str(status))
        elif entity == 'human':
            if status == 'completed':
                logging.info('(callstatus) call: ' + callSid + ' to ' + calledNumber + ' Status: ' + str(status))
                # TODO Create CDR
                generate_cdr(callType)
            else:
                logging.error('(callstatus) call: ' + callSid + ' to ' + calledNumber + ' Status: ' + str(status))

        else:
            logging.warn('Entity unknown: ' + entity)

        return str(response)

    except Exception, e:
        logging.error('Exception found call status: ' + str(e))
        return str(response)

#Call Center handling calls
@dialer.route('/api/acd',methods=['POST'])
def acd():
	response = twilio.twiml.Response()
	response.enqueue("Main number queue", waitUrl="/api/wait")
	return str(response)



#After sending call to Queue play music and notify other agents
@dialer.route('/api/wait', methods=['POST'])
def wait():
    method = 'wait'
    logging.info(
        "------------------------------------------------------Call Wait------------------------------------------------------")

    # Twilio Response Object
    response = twilio.twiml.Response()

    callId = request.values.get('CallSid', None)
    status = request.values.get('CallStatus', None)

    response.say("Thank you for calling Ramen Labs. Your call is very important to us, one representative will be with you shortly")
    response.say("You are number %s in the queue" % request.form['QueuePosition'])
    response.play("http://demo.brooklynhacker.com/music/christmas.mp3")

    account_sid = config.get('Twilio', 'account_sid')
    auth_token = config.get('Twilio', 'auth_token')

    client = TwilioRestClient(account_sid, auth_token)
    client.sms.messages.create(to="+14082186575", from_="+14157952944",
                               body='Customer is waiting in the Queue. Please call to help! - Customer callback # ' + str(request.values.get('Called', None)))
    logging.info("Customer " + str(request.values.get('Called', None)) +  " is number %s in the queue" % request.form['QueuePosition'])

    return str(response)

@dialer.route('/api/agent',methods=['POST'])
def agent():
	response = twilio.twiml.Response()
	with response.dial() as dial:
		dial.queue("Main number queue")
	return str(response)


@dialer.route("/api/connectagent", methods=['GET', 'POST'])
def connectagent():
    logging.info(
        "------------------------------------------------------Call Agent------------------------------------------------------")

# Validate Destination format:
# Valid formats: E164 number, SIP URI

# Locate valid agent in configuration file
def locate_agent(customerTelephoneNumber):
    logging.info(
        "------------------------------------------------------Locate Agent------------------------------------------------------")
    #Reading agent system configuration
    try:

        #TODO Implement location algorithm

        #agent = ast.literal_eval(config.get('Agents', 'agent0'))
        agentInformation = ast.literal_eval(config.get('Agents', 'agentInformation'))
        agentList =	agentInformation['agents']
        for agent in [agent for agent in agentList]:
	        if agent['id']=='0':
		        agentTelephoneNumber = agent['phone']

        if validate_api_request('',agentTelephoneNumber,0) == 0:
            logging.info('Connecting customer: ' + customerTelephoneNumber + ' to an available agent...')
            #Find a valid agent and connect call
            connect(agent, agentTelephoneNumber, customerTelephoneNumber)
        else:
            logging.error('Invalid destination in agent configuration: ' + str(agentTelephoneNumber))
    except Exception, e:
        logging.error('Exception found locating agent' + str(e))

def generate_cdr(record):
    logging.info(
        "------------------------------------------------------Generate CDR------------------------------------------------------")
    print 'generate cdr'


# Catch all
@dialer.route("/", methods=['GET', 'POST'])
def index():
    from_number = request.values.get('From', None)
  
    if from_number in callers:
        caller = callers[from_number]
        logging.info("Call received from known calling party: " + str(from_number))
    else:
        logging.info("Call received from unknow calling party: " + str(from_number))

    response = twilio.twiml.Response()

    response.dial((config.get('System', 'zendesk')),
            action= config.get('System', 'url') + '/api/callstatus' + '?CallType=2',
            method='POST',
            timeLimit=int(config.get('Twilio', 'maxDuration')),
            timeout=int(config.get('Twilio', 'answerTooLate')))

    # If the dial fails:
    response.say("La llamada ha fallado",language="es")
    		
    return str(response)

@dialer.route("/api/handle-key", methods=['GET', 'POST'])
def handle_key():
    """Handle key press from a user."""
    # Get the digit pressed by the user
    digit_pressed = request.values.get('Digits', None)
    if digit_pressed == "1":
        response = twilio.twiml.Response()
        # Dial 1(408)2186575 - connect that number to the incoming caller.
        response.dial("+14082186575",
                      action=config.get('System', 'url') + '/api/callstatus' + '?CallType=2',
                      method='POST',
                      timeLimit=int(config.get('Twilio', 'maxDuration')),
                      timeout=int(config.get('Twilio', 'answerTooLate')))
        # If the dial fails:
        response.say("La llamada ha fallado",language="es")

        return str(response)

    # If the caller pressed anything but 1, redirect them to the homepage.
    else:
        return redirect("/")

########################################################################################################################

def validate_api_request(method,param,type):

    # Type  0 - E164 or sip uri
    #       1 - Date            2002-10-27 06:00:00 EST-0500 | now
    #       2 - String
    #       3 - Numeric


    logging.info('Method: ' + method + ' Param: ' + param + ' Type: ' + str(type))

    ### Validating predefined methods
    if method == 'dial':
        if type == 0:
            if isinstance(param, str) and param != None and len(param) > 1:
                if len(param) < 48:
                    return 0
                else:
                    return -1
            else:
                return -1

        elif type == 1:
            if isinstance(param, str) and param != None and len(param) > 1:
                if param.lower() == 'now':
                    return 0
                else:
                    return -1
            else:
                return -1

        elif type == 2:
            if isinstance(param, str):
               return 0
            else:
                return -1


        elif type == 3:
            if isinstance(param, int):
               return 0
            else:
                return -1
        else:
            return -1


    if method == '':
        if type == 0:
            if isinstance(param, str) and param != None and len(param) > 1:
                if len(param) < 48:
                    return 0
                else:
                    return -1
            else:
                return -1
        elif type == 1:
            if isinstance(param, int):
                return 0
            else:
                return -1
        else:
            return -1

#Handle Errors
def errorRequest(method, code, http_error):
    resp = {'request': method, 'code': str(errorHandler(code))}
    #make_response(jsonify({'Dial': 'Invalid Destination'}), 404)
    logging.error(resp)
    return make_response(jsonify(resp), http_error)

#Error codes
def errorHandler(err):
    systemErrors = {
        1: 'Method not supported',
        2: 'Duplicate agent name',
        4: 'No such conference or auto attendant',
        5: 'No such agent',
        6: 'Too many conferences.',
        8: 'No conference name or auto attendant id supplied',
        10: 'No participant address supplied',
        11: 'Invalid destination',
        13: 'Invalid PIN specified',
        15: 'Insufficient privileges',
        16: 'Invalid enumerateID value',
        17: 'Port reservation failure',
        18: 'Duplicate numeric ID',
        20: 'Unsupported participant type',
        25: 'New port limit lower than currently active',
        34: 'Internal error',
        35: 'String is too long',
        101: 'Missing parameter',
        102: 'Invalid parameter',
        103: 'Malformed parameter',
        105: 'Request too large',
        201: 'Operation failed',
        202: 'Product needs its activation feature key',
        203: 'Too many asynchronous requests',

    }
    return systemErrors[err]

# Main
def main():
    #Initialize logging framework
    try:
        #Reading logFile location
        #absPath = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))), os.pardir))
        logFile = config.get('System', 'logfile')
        if logFile == '' or logFile == None:logFile = "app.log"

        listeningInterface = config.get('System', 'hostName')
        if listeningInterface == '' or listeningInterface == None:host = '0.0.0.0'

        listeningPort = int(os.environ.get('PORT', 8081))
        if listeningPort == '' or listeningPort == None or not isinstance(int(listeningPort), int):listeningPort = 8081

        logging.basicConfig(filename=logFile,
                            level=logging.INFO,
                            format='%(asctime)s.%(msecs).03d %(levelname)s %(message)s',
                            datefmt='%m/%d/%Y %I:%M:%S')

        logging.info(
            '-----------------------------------------------Initializing dialer server-----------------------------------------------')
        print '-----------------------------------------------Initializing dialer server-----------------------------------------------'
        logging.info(' * Starting call forward server' + ' version: ' + config.get('System', 'version'))
        print ' * Starting forward server' + ' version: ' + config.get('System', 'version')
        dialer.run(host=listeningInterface, port=int(listeningPort), debug=True, use_reloader=False)

    except Exception, e:
        print 'Exception found during app initialization ' + str(e)
        logging.exception("Exception found during server app initialization " + str(e))

if __name__ == "__main__":
    main()
