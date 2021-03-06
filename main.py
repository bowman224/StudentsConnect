#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import uuid
import datetime
import logging
from django.utils import simplejson
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from google.appengine.api import channel

class ConnectedUser(db.Model):
  client_id    = db.StringProperty()
  name         = db.StringProperty()
  school       = db.StringProperty()
  language    = db.StringProperty()
  last_present = db.DateTimeProperty()

class MainHandler(webapp.RequestHandler):
  def get(self):
    template_values = {'client_id': uuid.uuid1()}
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    self.response.out.write(template.render(path, template_values))

  def post(self):
      client_id = escape(self.request.get('client_id'))
      new_user = ConnectedUser( client_id = client_id,
                                name      = escape(self.request.get('name')),
                                school    = escape(self.request.get('school')),
                                language = escape(self.request.get('language')) )
      new_user.put()
      self.redirect('/chat?client_id=' + client_id)
      
class ChatHandler(webapp.RequestHandler):
  def get(self):
    client_id = self.request.get("client_id")
    if client_id:
      current_user = ConnectedUser.all().filter("client_id = ", client_id).get()
      if current_user:
        token = channel.create_channel(client_id)
        connected_users = ConnectedUser.all().fetch(50)

	flash_path = os.path.join(os.path.dirname(__file__),'flash/bin-debug/studentsconnect.html')
	flash_content = template.render(flash_path, {})
    template_values = {
      'current_user': current_user,
      'connected_users': connected_users,
      'token': token ,
      'flash_content': flash_content
    }
    path = os.path.join(os.path.dirname(__file__), 'chat.html')
    self.response.out.write(template.render(path, template_values))

  def post(self):
    for user in ConnectedUser.all():
      channel.send_message(user.client_id, self.request.get('msg'))

class PresenceHandler(webapp.RequestHandler):
  def post(self):
    client_id = self.request.get('client_id')
    present_user = ConnectedUser.all().filter("client_id = ", client_id).get()
    if present_user:
      present_user.last_present = datetime.datetime.now()
      present_user.put()
      
    present_users = ConnectedUser.all().filter("last_present > ", 
                                                datetime.datetime.now() - datetime.timedelta(seconds=6)).fetch(50)
    for user in present_users: # only notify present users?
      present_users_info = map(lambda u: {"client_id": u.client_id, 
										  "name": u.name, 
										  "school": u.school, 
										  "language": u.language}, present_users)
      channel.send_message(user.client_id, simplejson.dumps({"present_users": present_users_info}))

class ChatRequestHandler(webapp.RequestHandler):
  def post(self):
    client_id = self.request.get('client_id')
    requestor_id = self.request.get('requestor_id')
    channel.send_message(client_id, simplejson.dumps({"chat_request": requestor_id}))
    print "ChatRequestHandler"

class ChatConfirmationHandler(webapp.RequestHandler):
  def post(self):
	client_id = self.request.get('client_id')
	confirm_id = self.request.get('confirm_id')
	channel.send_message(client_id, simplejson.dumps({"confirmed_request": confirm_id}))

#Escape form entries
def escape(value):
  html_escape_table = {
    "&": "&amp;",
    '"': "&quot;",
    "'": "&apos;",
    ">": "&gt;",
    "<": "&lt;",
    }

  """Produce entities within text."""
  return "".join(html_escape_table.get(c,c) for c in value)


def main():
  application = webapp.WSGIApplication([
                    ('/', MainHandler),
                    ('/chat', ChatHandler),
                    ('/presence', PresenceHandler),
                    ('/request_chat', ChatRequestHandler),
                    ('/confirm_chat',ChatConfirmationHandler)],
                    debug=True)
  util.run_wsgi_app(application)

if __name__ == '__main__':
  main()
