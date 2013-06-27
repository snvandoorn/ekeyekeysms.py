import os
import cgi
import datetime
import urllib
import wsgiref.handlers
import re
import logging

from google.appengine.api.urlfetch  import *
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

class SMS(db.Model):  
  """Models an individual SMS entry with an author, content, and date."""  
  msgid = db.StringProperty(multiline=False)
  to    = db.StringProperty(multiline=False)
  text  = db.StringProperty(multiline=True)
  status= db.StringProperty(multiline=True)
  date  = db.DateTimeProperty(auto_now_add=True)

def guestbook_key(guestbook_name=None):
  """Constructs a Datastore key for a SMS entity with guestbook_name."""
  return db.Key.from_path('SMS', guestbook_name or 'default')

class MainPage(webapp.RequestHandler):
  def get(self):
    logging.info('Starting Main handler')
    # Ancestor queries, as shown here, are strongly consistent; queries that
    # span entity groups are only eventually consistent. If we omitted the
    # ancestor from this query, there would be a slight chance that a greeting
    # that had just been written would not show up in a query.
    smss = db.GqlQuery("SELECT * "
                            "FROM SMS "
                            "WHERE ANCESTOR IS :1 "
                            "ORDER BY date DESC LIMIT 10",
                            guestbook_key())
    if users.get_current_user():
      url = users.create_logout_url(self.request.uri)
      url_linktext = 'Logout'        
    else:
      url = users.create_login_url(self.request.uri)
      url_linktext = 'Login'
        
    template_values = {'smss': smss,
                'url': url,            
                'url_linktext': url_linktext,
                        }
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    self.response.out.write(template.render(path, template_values))
    logging.info('Ending Main handler')

       
       
       

#"No_Credit" - there is not enought credit in your account to send the message.
#"Unauthorized" - your credentials are incorrect.
#"0" - there was a problem sending the message.
#"1 , n , id , c" - the messgae was sent successfully. In that case, n is the number of messages that were actually sent (in case the message was long and had to broken to several SMSs), id - the unique message id. You need to register this number in case you would like to receive delivery reports (see below), c - the remaining credit in your account.          
class SendSMS(webapp.RequestHandler):
  def post(self):
    logging.info('Starting SendSMS')
    # We set the same parent key on the 'SMS' to ensure each sms is in
    # the same entity group. Queries across the single entity group will be
    # consistent. However, the write rate to a single entity group should
    # be limited to ~1/second.
    sms = SMS(parent=guestbook_key())
#    if users.get_current_user():
#      greeting.author = users.get_current_user().nickname()
    pwd = self.request.get('pwd')
    sms.to   = self.request.get('to')
    sms.text = self.request.get('text')
#    url = 'http://localhost:8080/smsgate'
#    url = 'https://misronim.appspot.com/smsgate'
    url = 'https://misronim.appspot.com/smsgate'
    form_fields = { 
                'user':'snvandoorn@googlemail.com',
                'pwd': pwd,          #-- 4fun@mm!
                'to':  sms.to,
                'txt': cgi.escape(sms.text)
                }
    form_data = urllib.urlencode(form_fields)
    ret = fetch(url, payload=form_data,method=POST, 
                headers={'Content-Type': 'application/x-www-form-urlencoded'}, 
                allow_truncated=False, follow_redirects=True, 
                deadline=50, validate_certificate=True)
#     content: string containing the response from the server
#     status_code: HTTP status code returned by the server
#     headers: dictionary of headers returned by the server
    sms.status = 'code:-{0}- content:-{1}-'.format(ret.status_code,ret.content)
    if ret.status_code >= 200 and ret.status_code < 300:
      list = ret.content.split(',')
      if list[0] == '1' :
        sms.msgid  = list[2]
      sms.put()    
      logging.info('SendSMS succeeded:code:{0} content:{1}'.format(ret.status_code,ret.content))
    else:
      logging.info('SendSMS failed:code:{0} content:{1}'.format(ret.status_code,ret.content))
    logging.info('Ending SendSMS')
    template_values = {
      'url' : url
      ,'to' : sms.to
      ,'text' : sms.text
      ,'status_code' : ret.status_code
      ,'content' : ret.content
      ,'url_linktext' : 'SMS send status updates'
      }
    path = os.path.join(os.path.dirname(__file__), 'sendsms.html')
    self.response.out.write(template.render(path, template_values))
    
      


#http://snvandoornsms.appspot.com/ReceivingSMSDeliveryReports
#Receiving delivery reports:
#In case you chose to receive delivery reports, These will be sent to the URL registered for that purpose on your account.
#This should be the URL of a listener routine on your server or app. Our system will HTTP POST the delivery reports to this URL with two parameters you should extract:
#"msgid" - the unique message id.
#"status" - message status. This can be one of the following: DELIVRD - message delivered. UNDELIV - message undeliverable. EXPIRED - messgae could not be delivered and will not be retried. REJECTED - message rejected by target operator.
class ReceivingSMSDeliveryReports(webapp.RequestHandler):
  def post(self):
    logging.info('Starting ReceivingSMSDeliveryReports.post')
    # We set the same parent key on the 'SMS' to ensure each sms is in
    # the same entity group. Queries across the single entity group will be
    # consistent. However, the write rate to a single entity group should
    # be limited to ~1/second.
    msgid = self.request.get('msgid')
    status = self.request.get('status')
    smss = db.GqlQuery("SELECT * "
                            "FROM SMS "
                            "WHERE ANCESTOR IS :1 "
                            "AND msgid=:2"
#                           "ORDER BY date DESC"
                           " LIMIT 1",
                            guestbook_key(),msgid)
    if smss:
      sms = smss[0]
      sms.status = status
      db.put(sms)
    logging.info('Ending ReceivingSMSDeliveryReports.post')
      
  def get(self):
    # We set the same parent key on the 'SMS' to ensure each sms is in
    # the same entity group. Queries across the single entity group will be
    # consistent. However, the write rate to a single entity group should
    # be limited to ~1/second.
    logging.info('Starting ReceivingSMSDeliveryReports.get')
    msgid = self.request.get('msgid')
    status = self.request.get('status')
    logging.info('ReceivingSMSDeliveryReports.get status update:{0}:{1}'.format(msgid,status))
    smss = db.GqlQuery("SELECT * "
                            "FROM SMS "
                            "WHERE ANCESTOR IS :1 "
                            "AND msgid=:2"
 #                           "ORDER BY date DESC"
                            " LIMIT 1"
                            ,guestbook_key()
                            ,msgid)
    if smss:
      sms = smss[0]
      logging.info('sms.get:{0}:{1}:{2}:{3}'.format(sms.msgid,sms.to,sms.status,sms.date))
      sms.status = status
      db.put(sms)
      logging.info('sms.put:{0}:{1}:{2}:{3}'.format(sms.msgid,sms.to,sms.status,sms.date))
      self.redirect('/')
      logging.info('ReceivingSMSDeliveryReports.get status updated:{0}:{1}'.format(msgid,status))
    logging.info('Ending ReceivingSMSDeliveryReports.get')
    
    
    
application = webapp.WSGIApplication(
                [('/', MainPage)
                ,('/sendsms', SendSMS)
                ,('/ReceivingSMSDeliveryReports', ReceivingSMSDeliveryReports)
                ],
                                                      debug=True)
def main():
  run_wsgi_app(application)

if __name__ == "__main__":
    main()
