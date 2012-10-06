#
# Functional test
#
# Requires WebTest http://webtest.pythonpaste.org/
# sudo aptitude install python-webtest
#
# Run as: nosetests functional_test_mongo.py
#

from nose.tools import assert_raises, raises, with_setup
from time import time
from datetime import datetime
from webtest import TestApp
import glob
import os, sys, inspect
import shutil

from cork import Cork, MongoDbBackend

REDIR = '302 Found'
app = None
tmpdir = None
orig_dir = None
tmproot = None

if sys.platform == 'darwin':
    tmproot = "/tmp"
else:
    tmproot = "/dev/shm"

# somehow previous test forgets the directory we started from.
# http://stackoverflow.com/questions/2632199/how-do-i-get-the-path-of-the-current-executed-file-in-python
#def foo():
#    pass
#def module_path(local_function):
#    ''' returns the module path without the use of __file__.  Requires a function defined
#   locally in the module.
#   from http://stackoverflow.com/questions/729583/getting-file-path-of-imported-module'''
#    return os.path.abspath(inspect.getsourcefile(local_function))
#orig_dir = module_path(foo)

orig_dir = os.path.abspath(os.path.dirname(__file__))

def initialize_database():
    """Populate a directory with valid configuration files, to be run just once
    The files are not modified by each test
    """
    backend = MongoDbBackend(
        server = "localhost",
        port = 27017,
        database = "sample_webapp",
        initialize=True,
        users_store="users",
        roles_store="roles",
        pending_regs_store="register",
    )
    cork = Cork(backend)

    cork._store.roles['admin'] = 100
    cork._store.roles['editor'] = 60
    cork._store.roles['user'] = 50

    tstamp = str(datetime.utcnow())
    username = password = 'admin'
    cork._store.users[username] = {
        'username': username,
        'role': 'admin',
        'hash': cork._hash(username, password),
        'email_addr': username + '@localhost.local',
        'desc': username + ' test user',
        'creation_date': tstamp
    }
    username = password = 'user'
    cork._store.users[username] = {
        'username': username,
        'role': 'user',
        'hash': cork._hash(username, password),
        'email_addr': username + '@localhost.local',
        'desc': username + ' test user',
        'creation_date': tstamp
    }


def remove_temp_dir():
    for f in glob.glob('%s/cork_functional_test_wd*' % tmproot, ):
        shutil.rmtree(f)

def setup_app():

    # create test dir and populate it using the example files
    global tmpdir
    global orig_dir

    # Initialize the MongoDb database
    initialize_database()

    # purge the temporary test directory
    remove_temp_dir()

    # populate the temporary test dir
    tstamp = str(time())[5:]
    tmpdir = "%s/cork_functional_test_wd_%s" % (tmproot, tstamp)
    os.mkdir(tmpdir)

    # copy the needed files
    tmp_source = "%s/cork_functional_test_source" % tmproot
    shutil.copytree(orig_dir + '/views', tmpdir + '/views')
    os.chdir(tmpdir)

    # create global TestApp instance
    global app
    import simple_webapp
    simple_webapp.configure(backend_type="mongobackend")
    app = TestApp(simple_webapp.app)

def login():
    """run setup_app and log in"""
    global app
    setup_app()
    p = app.post('/login', {'username': 'admin', 'password': 'admin'})

def teardown():
    remove_temp_dir()
    app = None

@with_setup(login, teardown)
def test_functional_login():
    # fetch a page successfully
    assert app.get('/admin').status == '200 OK'

@with_setup(setup_app, teardown)
def test_login_existent_user_none_password():
    p = app.post('/login', {'username': 'admin', 'password': None})
    assert p.status == REDIR, "Redirect expected"
    assert p.location == 'http://localhost:80/login',\
    "Incorrect redirect to %s" % p.location

@with_setup(setup_app, teardown)
def test_login_nonexistent_user_none_password():
    p = app.post('/login', {'username': 'IAmNotHere', 'password': None})
    assert p.status == REDIR, "Redirect expected"
    assert p.location == 'http://localhost:80/login',\
    "Incorrect redirect to %s" % p.location

@with_setup(setup_app, teardown)
def test_login_existent_user_empty_password():
    p = app.post('/login', {'username': 'admin', 'password': ''})
    assert p.status == REDIR, "Redirect expected"
    assert p.location == 'http://localhost:80/login',\
    "Incorrect redirect to %s" % p.location

@with_setup(setup_app, teardown)
def test_login_nonexistent_user_empty_password():
    p = app.post('/login', {'username': 'IAmNotHere', 'password': ''})
    assert p.status == REDIR, "Redirect expected"
    assert p.location == 'http://localhost:80/login',\
    "Incorrect redirect to %s" % p.location

@with_setup(setup_app, teardown)
def test_login_existent_user_wrong_password():
    p = app.post('/login', {'username': 'admin', 'password': 'BogusPassword'})
    assert p.status == REDIR, "Redirect expected"
    assert p.location == 'http://localhost:80/login',\
    "Incorrect redirect to %s" % p.location

@with_setup(setup_app, teardown)
def test_functional_login_logout():
    # Incorrect login
    p = app.post('/login', {'username': 'admin', 'password': 'BogusPassword'})
    assert p.status == REDIR
    assert p.location == 'http://localhost:80/login',\
    "Incorrect redirect to %s" % p.location

    # log in and get a cookie
    p = app.post('/login', {'username': 'admin', 'password': 'admin'})
    assert p.status == REDIR
    assert p.location == 'http://localhost:80/',\
    "Incorrect redirect to %s" % p.location

    # fetch a page successfully
    assert app.get('/admin').status == '200 OK'

    # log out
    assert app.get('/logout').status == REDIR

    # drop the cookie
    app.reset()
    assert app.cookies == {}, "The cookie should be gone"

    # fetch the same page, unsuccessfully
    assert app.get('/admin').status == REDIR

@with_setup(login, teardown)
def test_functional_expiration():
    assert app.get('/admin').status == '200 OK'
    # change the cookie expiration in order to expire it
    app.app.options['timeout'] = 0
    assert app.get('/admin').status == REDIR, "The cookie should have expired"
