# -*- coding: utf-8 -*-
from plone.app.content.testing import PLONE_APP_CONTENT_AT_FUNCTIONAL_TESTING
from plone.app.content.testing import PLONE_APP_CONTENT_DX_FUNCTIONAL_TESTING
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import login
from plone.app.testing import logout
from plone.app.testing import setRoles
from plone.testing.z2 import Browser
from plone.locking.interfaces import ILockable
from zExceptions import Unauthorized
from z3c.form.interfaces import IFormLayer
from zope.component import getMultiAdapter
from zope.interface import alsoProvides

import transaction
import unittest


class ActionsDXTestCase(unittest.TestCase):

    layer = PLONE_APP_CONTENT_DX_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.request = self.layer['request']

        self.portal.acl_users.userFolderAddUser(
            'editor', 'secret', ['Editor'], [])

        # For z3c.forms request must provide IFormLayer
        alsoProvides(self.request, IFormLayer)

        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.portal.invokeFactory(
            type_name='Folder', id='f1', title='A Test Folder')

        transaction.commit()
        self.browser = Browser(self.layer['app'])
        self.browser.handleErrors = False
        self.browser.addHeader(
            'Authorization', 'Basic {0}:{1}'.format(TEST_USER_NAME, 'secret'))

    def tearDown(self):
        if 'f1' in self.portal.objectIds():
            self.portal.manage_delObjects(ids='f1')
            transaction.commit()

    def test_delete_confirmation(self):
        folder = self.portal['f1']

        form = getMultiAdapter(
            (folder, self.request), name='delete_confirmation')
        form.update()

        cancel = form.buttons['Cancel']
        form.handlers.getHandler(cancel)(form, form)

        self.assertFalse(form.is_locked)

    def test_delete_confirmation_if_locked(self):
        folder = self.portal['f1']
        lockable = ILockable.providedBy(folder)

        form = getMultiAdapter(
            (folder, self.request), name='delete_confirmation')
        form.update()

        self.assertFalse(form.is_locked)

        if lockable:
            lockable.lock()

        form = getMultiAdapter(
            (folder, self.request), name='delete_confirmation')
        form.update()

        self.assertFalse(form.is_locked)

        # After switching the user it should not be possible to delete the
        # object. Of course this is only possible if our context provides
        # ILockable interface.
        if lockable:
            logout()
            login(self.portal, 'editor')

            form = getMultiAdapter(
                (folder, self.request), name='delete_confirmation')
            form.update()
            self.assertTrue(form.is_locked)

            logout()
            login(self.portal, TEST_USER_NAME)

            ILockable(folder).unlock()

    def test_delete_confirmation_cancel(self):
        folder = self.portal['f1']

        self.browser.open(folder.absolute_url() + '/delete_confirmation')
        self.browser.getControl(name='form.buttons.Cancel').click()
        self.assertEqual(self.browser.url, folder.absolute_url())

    def test_rename_form(self):
        logout()
        folder = self.portal['f1']

        # We need zope2.CopyOrMove permission to rename content
        self.browser.open(folder.absolute_url() + '/folder_rename')
        self.browser.getControl(name='form.widgets.new_id').value = 'f2'
        self.browser.getControl(name='form.widgets.new_title').value = 'F2'
        self.browser.getControl(name='form.buttons.Rename').click()
        self.assertEqual(folder.getId(), 'f2')
        self.assertEqual(folder.Title(), 'F2')
        self.assertEqual(self.browser.url, folder.absolute_url())

        login(self.portal, TEST_USER_NAME)
        self.portal.manage_delObjects(ids='f2')
        transaction.commit()

    def test_rename_form_cancel(self):
        folder = self.portal['f1']

        _id = folder.getId()
        _title = folder.Title()

        self.browser.open(folder.absolute_url() + '/folder_rename')
        self.browser.getControl(name='form.buttons.Cancel').click()
        transaction.commit()

        self.assertEqual(self.browser.url, folder.absolute_url())
        self.assertEqual(folder.getId(), _id)
        self.assertEqual(folder.Title(), _title)

    def _get_token(self, context):
        authenticator = getMultiAdapter(
            (context, self.request), name='authenticator')

        return authenticator.token()

    def test_object_cut_view(self):
        folder = self.portal['f1']

        # We need pass an authenticator token to prevent Unauthorized
        self.assertRaises(
            Unauthorized,
            self.browser.open,
            '{0:s}/object_cut'.format(folder.absolute_url())
        )

        # We need to have Copy or Move permission to cut an object
        self.browser.open('{0:s}/object_cut?_authenticator={1:s}'.format(
            folder.absolute_url(), self._get_token(folder)))

        self.assertIn('__cp', self.browser.cookies)
        self.assertIn(
            '{0:s} cut.'.format(folder.Title()), self.browser.contents)

    def test_object_copy_view(self):
        folder = self.portal['f1']

        # We need pass an authenticator token to prevent Unauthorized
        self.assertRaises(
            Unauthorized,
            self.browser.open,
            '{0:s}/object_copy'.format(folder.absolute_url())
        )

        self.browser.open('{0:s}/object_copy?_authenticator={1:s}'.format(
            folder.absolute_url(), self._get_token(folder)))

        self.assertIn('__cp', self.browser.cookies)
        self.assertIn(
            '{0:s} copied.'.format(folder.Title()), self.browser.contents)

    def test_object_cut_and_paste(self):
        folder = self.portal['f1']
        self.portal.invokeFactory(type_name='Document', id='d1', title='A Doc')
        doc = self.portal['d1']
        transaction.commit()

        self.browser.open('{0:s}/object_cut?_authenticator={1:s}'.format(
            doc.absolute_url(), self._get_token(doc)))

        self.assertIn('__cp', self.browser.cookies)
        self.assertIn('d1', self.portal.objectIds())
        self.assertIn('f1', self.portal.objectIds())

        # We need pass an authenticator token to prevent Unauthorized
        self.assertRaises(
            Unauthorized,
            self.browser.open,
            '{0:s}/object_paste'.format(folder.absolute_url())
        )

        self.browser.open('{0:s}/object_paste?_authenticator={1:s}'.format(
            folder.absolute_url(), self._get_token(doc)))

        self.assertIn('__cp', self.browser.cookies)
        transaction.commit()

        self.assertNotIn('d1', self.portal.objectIds())
        self.assertIn('d1', folder.objectIds())
        self.assertIn('Item(s) pasted.', self.browser.contents)

    def test_object_copy_and_paste(self):
        folder = self.portal['f1']
        folder.invokeFactory(type_name='Document', id='d1', title='A Doc')
        doc = folder['d1']
        transaction.commit()

        self.browser.open('{0:s}/object_copy?_authenticator={1:s}'.format(
            doc.absolute_url(), self._get_token(doc)))

        self.assertIn('__cp', self.browser.cookies)

        # We need pass an authenticator token to prevent Unauthorized
        self.assertRaises(
            Unauthorized,
            self.browser.open,
            '{0:s}/object_paste'.format(folder.absolute_url())
        )

        self.browser.open('{0:s}/object_paste?_authenticator={1:s}'.format(
            folder.absolute_url(), self._get_token(folder)))
        transaction.commit()

        self.assertIn('f1', self.portal.objectIds())
        self.assertIn('d1', folder.objectIds())
        self.assertIn('copy_of_d1', folder.objectIds())
        self.assertIn('Item(s) pasted.', self.browser.contents)

    def test_object_copy_and_paste_multiple_times(self):
        folder = self.portal['f1']
        folder.invokeFactory(type_name='Document', id='d1', title='A Doc')
        doc = folder['d1']
        transaction.commit()

        self.browser.open('{0:s}/object_copy?_authenticator={1:s}'.format(
            doc.absolute_url(), self._get_token(doc)))

        self.assertIn('__cp', self.browser.cookies)
        self.browser.open('{0:s}/object_paste?_authenticator={1:s}'.format(
            folder.absolute_url(), self._get_token(folder)))
        self.browser.open('{0:s}/object_paste?_authenticator={1:s}'.format(
            folder.absolute_url(), self._get_token(folder)))

        # Cookie should persist, because you can paste the item multiple times
        self.assertIn('__cp', self.browser.cookies)
        self.assertIn('f1', self.portal.objectIds())
        self.assertIn('d1', folder.objectIds())
        self.assertIn('copy_of_d1', folder.objectIds())
        self.assertIn('copy2_of_d1', folder.objectIds())
        self.assertIn('Item(s) pasted.', self.browser.contents)


class ActionsATTestCase(ActionsDXTestCase):

    layer = PLONE_APP_CONTENT_AT_FUNCTIONAL_TESTING
