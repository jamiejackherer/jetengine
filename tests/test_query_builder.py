import asyncio

from preggy import expect
import nose.tools

from jetengine import (
    Document,
    StringField,
    BooleanField,
    ListField,
    IntField,
    URLField,
    DateTimeField,
    Q,
    EmbeddedDocumentField,
)
from jetengine.query_builder.node import QCombination
from tests import AsyncTestCase, async_test


class EmbeddedDocument2(Document):
    test = StringField(db_field="else", required=False)


class EmbeddedDocument(Document):
    test = StringField(db_field="other", required=True)
    embedded2 = EmbeddedDocumentField(EmbeddedDocument2)


class User(Document):
    email = StringField(required=True)
    first_name = StringField(db_field="whatever", max_length=50, default=lambda: "Bernardo")
    last_name = StringField(max_length=50, default="Heynemann")
    is_admin = BooleanField(default=True)
    website = URLField(default="http://google.com/")
    updated_at = DateTimeField(required=True, auto_now_on_insert=True, auto_now_on_update=True)
    embedded = EmbeddedDocumentField(EmbeddedDocument, db_field="embedded_document")
    nullable = EmbeddedDocumentField(EmbeddedDocument, db_field="nullable_embedded_document")
    numbers = ListField(IntField())

    def __repr__(self):
        return "%s %s <%s>" % (self.first_name, self.last_name, self.email)


class TestQueryBuilder(AsyncTestCase):
    def setUp(self):
        super(TestQueryBuilder, self).setUp()
        self.drop_coll("User")

    def test_gets_proper_type(self):
        query = Q(first_name="Test")
        expect(query).to_be_instance_of(Q)

        query = Q(first_name="Test") | Q(first_name="Else")
        expect(query).to_be_instance_of(QCombination)

    def test_gets_proper_query(self):
        query = Q(first_name="Test")
        query_result = query.to_query(User)

        expect(query_result).to_be_like({"whatever": "Test"})

    def test_gets_proper_query_when_query_operator_used(self):
        query = Q(first_name__lte="Test")
        query_result = query.to_query(User)

        expect(query_result).to_be_like({"whatever": {"$lte": "Test"}})

    def test_gets_proper_query_when_embedded_document(self):
        query = Q(embedded__test__lte="Test")
        query_result = query.to_query(User)

        expect(query_result).to_be_like({"embedded_document.other": {"$lte": "Test"}})

    def test_gets_proper_query_when_embedded_document_in_many_levels(self):
        query = Q(embedded__embedded2__test__lte="Test")
        query_result = query.to_query(User)

        expect(query_result).to_be_like({"embedded_document.embedded2.else": {"$lte": "Test"}})

    def test_gets_proper_query_when_list_field(self):
        query = Q(numbers=[10])
        query_result = query.to_query(User)

        expect(query_result).to_be_like({"numbers": {"$all": [10]}})

    def test_gets_proper_query_when_and(self):
        query = Q(embedded__test__lte="Test") & Q(first_name="Someone")
        query_result = query.to_query(User)

        expect(query_result).to_be_like({"embedded_document.other": {"$lte": "Test"}, "whatever": "Someone"})

    def test_gets_proper_query_when_or(self):
        query = Q(first_name="Someone") | Q(first_name="Else")
        query_result = query.to_query(User)

        expect(query_result).to_be_like({"$or": [{"whatever": "Someone"}, {"whatever": "Else"}]})

    def test_gets_proper_query_when_many_operators(self):
        query = (Q(embedded__test__lte="Test") & Q(first_name="Someone")) | Q(first_name="Else")
        query_result = query.to_query(User)

        expect(query_result).to_be_like(
            {"$or": [{"embedded_document.other": {"$lte": "Test"}, "whatever": "Someone"}, {"whatever": "Else"}]}
        )

    def test_gets_proper_query_when_many_operators_with_and_first(self):
        query = Q(last_name="Whatever") & (
            (Q(embedded__test__lte="Test") & Q(first_name="Someone")) | Q(first_name="Else")
        )
        query_result = query.to_query(User)

        expect(query_result).to_be_like(
            {
                "$and": [
                    {"last_name": "Whatever"},
                    {
                        "$or": [
                            {"embedded_document.other": {"$lte": "Test"}, "whatever": "Someone"},
                            {"whatever": "Else"},
                        ]
                    },
                ]
            }
        )

    @nose.tools.nottest
    @asyncio.coroutine
    def create_test_users(self):
        self.user = yield from User.objects.create(
            email="heynemann@gmail.com",
            first_name="Bernardo",
            last_name="Heynemann",
            embedded=EmbeddedDocument(test="test"),
            nullable=None,
            numbers=[1, 2, 3],
        )

        self.user2 = yield from User.objects.create(
            email="heynemann@gmail.com",
            first_name="Someone",
            last_name="Else",
            embedded=EmbeddedDocument(test="test2"),
            nullable=EmbeddedDocument(test="test2"),
            numbers=[4, 5, 6],
        )

        self.user3 = yield from User.objects.create(
            email="heynemann@gmail.com",
            first_name="John",
            last_name="Doe",
            embedded=EmbeddedDocument(test="test3"),
            nullable=EmbeddedDocument(test="test3"),
            numbers=[7, 8, 9],
        )

    @async_test
    @asyncio.coroutine
    def test_can_query_using_q(self):
        yield from self.create_test_users()

        users = yield from User.objects.find_all()
        expect(users).to_length(3)

        users = yield from User.objects.filter(Q(first_name="Bernardo")).find_all()
        expect(users).to_length(1)

        users = yield from User.objects.filter(Q(first_name="Bernardo") | Q(first_name="Someone")).find_all()
        expect(users).to_length(2)

    @async_test
    @asyncio.coroutine
    def test_can_query_using_q_for_list(self):
        yield from User.objects.create(
            email="heynemann@gmail.com",
            first_name="Bernardo",
            last_name="Heynemann",
            embedded=EmbeddedDocument(test="test"),
            numbers=[1, 2, 3],
        )

        user2 = yield from User.objects.create(
            email="heynemann@gmail.com",
            first_name="Someone",
            last_name="Else",
            embedded=EmbeddedDocument(test="test2"),
            numbers=[4, 5, 6],
        )

        yield from User.objects.create(
            email="heynemann@gmail.com",
            first_name="John",
            last_name="Doe",
            embedded=EmbeddedDocument(test="test3"),
            numbers=[7, 8, 9],
        )

        users = yield from User.objects.filter(Q(numbers=[4])).find_all()
        expect(users).to_length(1)
        expect(users[0]._id).to_equal(user2._id)

        users = yield from User.objects.filter(Q(numbers=[5])).find_all()
        expect(users).to_length(1)
        expect(users[0]._id).to_equal(user2._id)

        users = yield from User.objects.filter(Q(numbers=[6])).find_all()
        expect(users).to_length(1)
        expect(users[0]._id).to_equal(user2._id)

        users = yield from User.objects.filter(Q(numbers=[4, 5, 6])).find_all()
        expect(users).to_length(1)
        expect(users[0]._id).to_equal(user2._id)

        users = yield from User.objects.filter(Q(numbers=[20])).find_all()
        expect(users).to_length(0)

    @async_test
    @asyncio.coroutine
    def test_can_query_using_q_with_is_null(self):
        yield from self.create_test_users()

        users = yield from User.objects.filter(Q(nullable__is_null=True)).find_all()
        expect(users).to_length(1)
        expect(users[0]._id).to_equal(self.user._id)

        users = yield from User.objects.filter(Q(nullable__is_null=False)).find_all()
        expect(users).to_length(2)
        expect(users[0]._id).to_equal(self.user2._id)
        expect(users[1]._id).to_equal(self.user3._id)

    def test_can_query_using_not_in(self):
        names = ["Someone", "John"]

        query = ~Q(first_name__in=names)
        query_result = query.to_query(User)

        expect(query_result).to_be_like({"whatever": {"$not": {"$in": ["Someone", "John"]}}})

    @async_test
    @asyncio.coroutine
    def test_can_query_using_not_in_with_real_users(self):
        yield from self.create_test_users()

        names = ["Someone", "John"]

        query = ~Q(first_name__in=names) & Q(last_name="Heynemann")

        users = yield from User.objects.filter(query).find_all()

        expect(users).to_length(1)
        expect(users[0].first_name).to_equal("Bernardo")
