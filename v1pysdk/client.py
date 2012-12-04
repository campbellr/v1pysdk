
import logging, time, base64
import urllib2
from urllib2 import Request, urlopen, HTTPError, HTTPBasicAuthHandler, HTTPCookieProcessor
from urllib import urlencode
from urlparse import urlunparse

try:
    from xml.etree import ElementTree
    from xml.etree.ElementTree import Element
except ImportError:
    from elementtree import ElementTree
    from elementtree.ElementTree import Element

AUTH_HANDLERS = [HTTPBasicAuthHandler]

try:
    from ntlm.HTTPNtlmAuthHandler import HTTPNtlmAuthHandler
except ImportError:
    logging.warn("Windows integrated authentication module (ntlm) not found.")
else:
    class CustomHTTPNtlmAuthHandler(HTTPNtlmAuthHandler):
        """ A version of HTTPNtlmAuthHandler that handles errors (better).

            The default version doesn't use `self.parent.open` in it's
            error handler, and completely bypasses the normal `OpenerDirector`
            call chain, most importantly `HTTPErrorProcessor.http_response`,
            which normally raises an error for 'bad' http status codes..
        """
        def http_error_401(self, req, fp, code, msg, hdrs):
            response = HTTPNtlmAuthHandler.http_error_401(self, req, fp, code, msg, hdrs)
            if not (200 <= response.code < 300):
                response = self.parent.error(
                        'http', req, response, response.code, response.msg,
                        response.info)
            return response

    AUTH_HANDLERS.append(CustomHTTPNtlmAuthHandler)




class V1Error(Exception): pass

class V1AssetNotFoundError(V1Error): pass

class V1Server(object):
  "Accesses a V1 HTTP server as a client of the XML API protocol"

  def __init__(self, address='localhost', instance='VersionOne.Web', username='', password=''):
    self.address = address
    self.instance = instance
    self.username = username
    self.password = password
    self._install_opener()
        
  def _install_opener(self):
    base_url = self.build_url('')
    password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, base_url, self.username, self.password)
    handlers = [HandlerClass(password_manager) for HandlerClass in AUTH_HANDLERS]
    self.opener = urllib2.build_opener(*handlers)
    self.opener.add_handler(HTTPCookieProcessor())

  def http_get(self, url):
    request = Request(url)
    response = self.opener.open(request)
    return response
  
  def http_post(self, url, data=''):
    request = Request(url, data)
    response = self.opener.open(request)
    return response
    
  def build_url(self, path, query='', fragment='', params='', port=80):
    "So we dont have to interpolate urls ad-hoc"
    path = self.instance + path
    if isinstance(query, dict):
      query = urlencode(query)
    url = urlunparse( ('http', self.address, path, params, query, fragment) )
    return url
    
  def fetch(self, path, query='', postdata=None):
    "Perform an HTTP GET or POST depending on whether postdata is present"
    url = self.build_url(path, query=query)
    try:
      if postdata is not None:
          if isinstance(postdata, dict):
              postdata = urlencode(postdata)
          response = self.http_post(url, postdata)
      else:
        response = self.http_get(url)
      body = response.read()
      return (None, body)
    except HTTPError, e:
      if e.code == 401:
          raise
      body = e.fp.read()
      return (e, body)
      
  def get_xml(self, path, query='', postdata=None):
    exception, body = self.fetch(path, query=query, postdata=postdata)
    document = ElementTree.fromstring(body)
    if exception:
      exception.xmldoc = document
      if exception.code == 404:
        raise V1AssetNotFoundError(exception)
      elif exception.code == 400:
        raise V1Error('\n'+body)
      else:
        raise V1Error(exception)
    return document
   
  def get_asset_xml(self, asset_type_name, oid):
    path = '/rest-1.v1/Data/{0}/{1}'.format(asset_type_name, oid)
    return self.get_xml(path)
    
  def get_query_xml(self, asset_type_name, where=None, sel=None):
    path = '/rest-1.v1/Data/{0}'.format(asset_type_name)
    query = {}
    if where is not None:
        query['Where'] = where
    if sel is not None:
        query['sel'] = sel        
    return self.get_xml(path, query=query)
    
  def get_meta_xml(self, asset_type_name):
    path = '/meta.v1/{0}'.format(asset_type_name)
    return self.get_xml(path)
    
  def execute_operation(self, asset_type_name, oid, opname):
    path = '/rest-1.v1/Data/{0}/{1}'.format(asset_type_name, oid)
    query = {'op': opname}
    return self.get_xml(path, query=query, postdata={})
    
  def get_attr(self, asset_type_name, oid, attrname):
    path = '/rest-1.v1/Data/{0}/{1}/{2}'.format(asset_type_name, oid, attrname)
    return self.get_xml(path)
  
  def create_asset(self, asset_type_name, xmldata, context_oid=''):
    body = ElementTree.tostring(xmldata, encoding="utf-8")
    query = {}
    if context_oid:
      query = {'ctx': context_oid}
    path = '/rest-1.v1/Data/{0}'.format(asset_type_name)
    return self.get_xml(path, query=query, postdata=body)
    
  def update_asset(self, asset_type_name, oid, update_doc):
    newdata = ElementTree.tostring(update_doc, encoding='utf-8')
    path = '/rest-1.v1/Data/{0}/{1}'.format(asset_type_name, oid)
    return self.get_xml(path, postdata=newdata)


  def get_attachment_blob(self, attachment_id, blobdata=None):
    path = '/attachment.v1/{0}'.format(attachment_id)
    exception, body = self.fetch(path, postdata=blobdata)
    if exception:
        raise exception
    return body
    
  set_attachment_blob = get_attachment_blob
  
    
    
  
    

