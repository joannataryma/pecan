.. _routing:

Controllers and Routing
=======================

When a user requests a certain URL in your app, how does Pecan know which
controller to route to? Pecan uses a routing strategy known as 
**object-dispatch** to map an HTTP request to a controller. 

Object-dispatch begins by splitting the
path into a list of components and then walking an object path, starting at
the root controller. You can imagine your application's controllers as a tree
of objects (branches of the object tree map directly to URL paths). Let's look 
at a simple bookstore application: 

::

    from pecan import expose

    class BooksController(object):
        @expose()
        def index(self):
            return "Welcome to book section."

        @expose()
        def bestsellers(self):
            return "We have 5 books in the top 10."

    class CatalogController(object):
        @expose()
        def index(self):
            return "Welcome to the catalog."

        books = BooksController()

    class RootController(object):
        @expose()
        def index(self):
            return "Welcome to store.example.com!"

        @expose()
        def hours(self):
            return "Open 24/7 on the web."

        catalog = CatalogController()

A request for ``/catalog/books/bestsellers`` from the online store would
begin with Pecan breaking the request up into ``catalog``, ``books``, and
``bestsellers``. Next, Pecan would lookup ``catalog`` on the root
controller. Using the ``catalog`` object, Pecan would then lookup
``books``, followed by ``bestsellers``. What if the URL ends in a slash?
Pecan will check for an ``index`` method on the current object. 

To illustrate further, the following paths...

::

    └── /
        ├── /hours
        └── /catalog
             └── /catalog/books
                └── /catalog/books/bestsellers

Would route to the following controller methods...

::

    └── RootController.index
        ├── RootController.hours
        └── CatalogController.index
             └── BooksController.index
                └── BooksController.bestsellers

Exposing Controllers
--------------------

At its core, ``@expose`` is how you tell Pecan which methods in a class
are publically-visible controllers. If a method is *not* decorated with
``@expose``, it will never be routed to.  ``@expose`` accepts three optional
parameters, some of which can impact routing and the content type of the
response body. 

::

    from pecan import expose

    class RootController(object):
        @expose(
            template        = None,
            content_type    = 'text/html',
            generic         = False
        )
        def hello(self):
            return 'Hello World' 


Let's look at an example using ``template`` and ``content_type``:

::

    from pecan import expose

    class RootController(object):
        @expose('json')
        @expose('text_template.mako', content_type='text/plain')
        @expose('html_template.mako')
        def hello(self):
            return {'msg': 'Hello!'}

You'll notice that we used three ``expose`` decorators. 

The first tells Pecan to serialize the response namespace using JSON
serialization when the client requests ``/hello.json``. 

The second tells Pecan to use the ``text_template.mako`` template file when the
client requests ``/hello.txt``. 

The third tells Pecan to use the html_template.mako template file when the 
client requests ``/hello.html``. If the client requests ``/hello``, Pecan will 
use the ``text/html`` content type by default.

Please see :ref:`pecan_decorators` for more information on ``@expose``.



Pecan's Routing Algorithm
-------------------------

Sometimes, the standard object-dispatch routing isn't adequate to properly
route a URL to a controller. Pecan provides several ways to short-circuit 
the object-dispatch system to process URLs with more control, including the
special ``_lookup``, ``_default``, and ``_route`` methods. Defining these
methods on your controller objects provides additional flexibility for 
processing all or part of a URL.


Setting a Return Status Code
--------------------------------

Setting a specific HTTP response code (such as ``201 Created``) is simple:

::

    from pecan import expose, response

    class RootController(object):

        @expose('json')
        def hello(self):
            response.status = 201
            return {'foo': 'bar'}

Pecan also comes with ``abort``, a utility function for raising HTTP errors:

::

    from pecan import expose, abort

    class RootController(object):

        @expose('json')
        def hello(self):
            abort(404)


Routing to Subcontrollers with ``_lookup``
------------------------------------------

The ``_lookup`` special method provides a way to process a portion of a URL, 
and then return a new controller object to route to for the remainder.

A ``_lookup`` method will accept one or more arguments, representing chunks
of the URL to be processed, split on ``/``, and then provide a ``*remainder`` list
which will be processed by the returned controller via object-dispatch.

Additionally, the ``_lookup`` method on a controller is called as a last
resort, when no other controller matches the URL via standard object-dispatch.

::

    from pecan import expose, abort
    from somelib import get_student_by_name

    class StudentController(object):
        def __init__(self, student):
            self.student = student

        @expose()
        def name(self):
            return self.student.name

    class RootController(object):
        @expose()
        def _lookup(self, primary_key, *remainder):
            student = get_student_by_primary_key(primary_key)
            if student:
                return StudentController(student), remainder
            else:
                abort(404)

An HTTP GET request to ``/8/name`` would return the name of the student
where ``primary_key == 8``.

Falling Back with ``_default``
------------------------------

The ``_default`` controller is called as a last resort when no other controller 
methods match the URL via standard object-dispatch.

::

    from pecan import expose

    class RootController(object):
        @expose()
        def english(self):
            return 'hello'

        @expose()
        def french(self):
            return 'bonjour'

        @expose()
        def _default(self):
            return 'I cannot say hello in that language'


...so in the example above, a request to ``/spanish`` would route to 
``RootController._default``.
            

Defining Customized Routing with ``_route``
-------------------------------------------

The ``_route`` method allows a controller to completely override the routing 
mechanism of Pecan. Pecan itself uses the ``_route`` method to implement its
``RestController``. If you want to design an alternative routing system on 
top of Pecan, defining a base controller class that defines a ``_route`` method
will enable you to have total control.


Mapping Controller Arguments
----------------------------

In Pecan, HTTP ``GET`` and ``POST`` variables that are `not` consumed 
during the routing process can be passed onto the controller as arguments.

Depending on the signature of your controller, these arguments can be mapped
explicitly to method arguments:

::

    from pecan import expose

    class RootController(object):
        @expose()
        def index(self, arg):
            return arg

        @expose()
        def kwargs(self, **kwargs):
            return str(kwargs)

::

    $ curl http://localhost:8080/?arg=foo
    foo
    $ curl http://localhost:8080/kwargs?a=1&b=2&c=3
    {u'a': u'1', u'c': u'3', u'b': u'2'}

...or can be consumed positionally:

::

    from pecan import expose

    class RootController(object):
        @expose()
        def args(self, *args):
            return ','.join(args)

::

    $ curl http://localhost:8080/args/one/two/three
    one,two,three

The same effect can be achieved with HTTP ``POST`` body variables:

::

    from pecan import expose

    class RootController(object):
        @expose()
        def index(self, arg):
            return arg

::

    $ curl -X POST "http://localhost:8080/" -H "Content-Type: application/x-www-form-urlencoded" -d "arg=foo"
    foo

Helper Functions
----------------

Pecan also provides several useful helper functions for moving between
different routes. The ``redirect`` function allows you to issue internal or 
``HTTP 302`` redirects.  The ``redirect`` utility, along with several other 
useful helpers, are documented in :ref:`pecan_core`.
