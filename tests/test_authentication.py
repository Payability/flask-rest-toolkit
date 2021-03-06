import json
import unittest
import base64

from flask import Flask, Request
from werkzeug.test import EnvironBuilder
from werkzeug.exceptions import Unauthorized

from flask_rest_toolkit.api import Api
from flask_rest_toolkit.endpoint import ApiEndpoint
from flask_rest_toolkit.auth import (
    BasicAuth, And, NoAuthorizationStrategy,
    AuthenticationStrategy)

try:
    from unittest import mock
except ImportError:
    import mock


class BasicAuthUnitTestCase(unittest.TestCase):
    def test_authorization_raises_exception_if_user_is_not_valid(self):
        "Should raise an Unauthorized exception if is_valid_user function returns False"
        is_valid_mock = mock.MagicMock(return_value=False)

        builder = EnvironBuilder()
        request = Request(builder.get_environ())
        request.authorization = {'username': 'john', 'password': 'xxx'}
        with self.assertRaises(Unauthorized):
            BasicAuth(is_valid_user=is_valid_mock).authenticate(request)

        is_valid_mock.assert_called_once_with('john', 'xxx')

    def test_authorization_raises_exception_if_authorization_is_not_set(self):
        "Should raise an exception and the is_valid_user function should never be invoked"
        is_valid_mock = mock.MagicMock(return_value=False)

        builder = EnvironBuilder()
        request = Request(builder.get_environ())
        request.authorization = None
        with self.assertRaises(Unauthorized):
            BasicAuth(is_valid_user=is_valid_mock).authenticate(request)

        self.assertEqual(is_valid_mock.call_count, 0)

    def test_authorization_passes_if_is_valid_user_returns_True(self):
        "Should return None if the user is valid"
        is_valid_mock = mock.MagicMock(return_value=True)

        builder = EnvironBuilder()
        request = Request(builder.get_environ())
        request.authorization = {'username': 'john', 'password': 'xxx'}

        result = BasicAuth(is_valid_user=is_valid_mock).authenticate(request)
        self.assertEqual(result, None)

        is_valid_mock.assert_called_once_with('john', 'xxx')


class DummyAuthentication(AuthenticationStrategy, NoAuthorizationStrategy):
    def __init__(self, valid_auth):
        self.valid_auth = valid_auth

    def authenticate(self, request):
        if not self.valid_auth:
            raise Unauthorized()


class AndAuthUnitTestCase(unittest.TestCase):
    def test_valid_authentication(self):
        is_valid_mock = mock.MagicMock(return_value=True)

        builder = EnvironBuilder()
        request = Request(builder.get_environ())
        request.authorization = {'username': 'john', 'password': 'xxx'}

        dummy = DummyAuthentication(valid_auth=True)
        dummy_auth_mock = mock.MagicMock(return_value=True)
        dummy.authenticate = dummy_auth_mock
        auth = And(
            BasicAuth(is_valid_user=is_valid_mock),
            dummy
        )

        result = auth.authenticate(request)
        self.assertEqual(result, None)

        is_valid_mock.assert_called_once_with('john', 'xxx')
        dummy_auth_mock.assert_called_once_with(request)

    def test_not_valid_authentication_second_auth_not_invoked(self):
        "Should raise an Unthorized exception and avoid invoking other auth strategies"
        is_valid_mock = mock.MagicMock(return_value=False)

        builder = EnvironBuilder()
        request = Request(builder.get_environ())
        request.authorization = {'username': 'john', 'password': 'xxx'}

        dummy = DummyAuthentication(valid_auth=True)
        dummy_auth_mock = mock.MagicMock(return_value=True)
        dummy.authenticate = dummy_auth_mock
        auth = And(
            BasicAuth(is_valid_user=is_valid_mock),
            dummy
        )

        with self.assertRaises(Unauthorized):
            auth.authenticate(request)

        is_valid_mock.assert_called_once_with('john', 'xxx')
        self.assertEqual(dummy_auth_mock.call_count, 0)


class BasicAuthTestCase(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        self.username = "testing@example.com"
        self.password = "ShowMeTheMoney"

        def is_valid_user(username, password):
            return (username, password) == (self.username, self.password)

        self.tasks = [
            {'id': 1, 'task': 'Do the laundry'},
            {'id': 2, 'task': 'Do the dishes'},
        ]

        def get_tasks(request):
            return self.tasks

        api_201409 = Api(version="v1")
        api_201409.register_endpoint(ApiEndpoint(
            http_method="GET",
            endpoint="/task/basic",
            handler=get_tasks,
            authentication=BasicAuth(is_valid_user=is_valid_user)
        ))

        app.register_blueprint(api_201409)

        app.config['TESTING'] = True
        self.app = app.test_client()

    def test_basic_auth_not_authenticated(self):
        resp = self.app.get(
            '/v1/task/basic',
            content_type='application/json')
        self.assertEqual(resp.status_code, 401)

    def test_basic_auth_authenticated(self):
        auth_str = "{username}:{password}".format(
            username=self.username, password=self.password).encode('ascii')
        resp = self.app.get(
            '/v1/task/basic',
            content_type='application/json',
            headers={
                'Authorization': b'Basic ' + base64.b64encode(auth_str)
            }
        )
        self.assertEqual(resp.status_code, 200)

        data = json.loads(resp.data.decode(resp.charset))
        self.assertEqual(data, self.tasks)

    def test_basic_auth_with_wrong_username_and_password(self):
        auth_str = "{username}:{password}".format(
            username="XXX", password="OOO").encode('ascii')
        resp = self.app.get(
            '/v1/task/basic',
            content_type='application/json',
            headers={
                'Authorization': b'Basic ' + base64.b64encode(auth_str)
            }
        )
        self.assertEqual(resp.status_code, 401)
