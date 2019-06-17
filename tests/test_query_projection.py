import asyncio
from preggy import expect

from jetengine import (
    Document,
    StringField,
    BooleanField,
    ListField,
    IntField,
    URLField,
    DateTimeField,
    EmbeddedDocumentField,
    ReferenceField,
)
from jetengine.query_builder.field_list import QueryFieldList
from jetengine.errors import LoadReferencesRequiredError, PartlyLoadedDocumentError
from tests import AsyncTestCase, async_test


class EmbeddedDocument2(Document):
    test = StringField(db_field="else", required=False)


class EmbeddedDocument(Document):
    test = StringField(db_field="other", required=True)
    embedded2 = EmbeddedDocumentField(EmbeddedDocument2)


class Category(Document):
    __collection__ = "categories"

    name = StringField(required=True)
    descr = StringField(required=True)


class Comment(Document):
    title = StringField(required=True)
    text = StringField(required=True)


class Post(Document):
    __collection__ = "posts"

    title = StringField(required=True)
    text = StringField(required=True, db_field="content")
    category = ReferenceField(reference_document_type=Category)
    comments = ListField(EmbeddedDocumentField(embedded_document_type=Comment))


class User(Document):
    __collection__ = "users"

    index = IntField(required=True)
    email = StringField(required=True)
    first_name = StringField(db_field="whatever", max_length=50, default=lambda: "Bernardo")
    last_name = StringField(max_length=50, default="Heynemann")
    is_admin = BooleanField(default=True)
    website = URLField(default="http://google.com/")
    updated_at = DateTimeField(required=True, auto_now_on_insert=True, auto_now_on_update=True)
    embedded = EmbeddedDocumentField(EmbeddedDocument, db_field="embedded_document")
    nullable = EmbeddedDocumentField(EmbeddedDocument, db_field="nullable_embedded_document")
    numbers = ListField(IntField())

    posts = ListField(ReferenceField(reference_document_type=Post))

    def __repr__(self):
        return "%s %s <%s>" % (self.first_name, self.last_name, self.email)


class TestQueryProjection(AsyncTestCase):
    def setUp(self):
        super(TestQueryProjection, self).setUp()
        self.drop_coll(User.__collection__)
        self.drop_coll(Post.__collection__)
        self.drop_coll(Category.__collection__)
        self.create_test_objects()

    @async_test
    @asyncio.coroutine
    def create_test_objects(self):
        self.user = yield from User.objects.create(
            index=1,
            email="heynemann@gmail.com",
            first_name="Bernardo",
            last_name="Heynemann",
            embedded=EmbeddedDocument(test="test"),
            nullable=None,
            numbers=[1, 2, 3],
        )

        self.user2 = yield from User.objects.create(
            index=2,
            email="heynemann@gmail.com",
            first_name="Someone",
            last_name="Else",
            embedded=EmbeddedDocument(test="test2", embedded2=EmbeddedDocument2(test="test22")),
            nullable=EmbeddedDocument(test="test2"),
            numbers=[4, 5, 6],
        )

        self.user3 = yield from User.objects.create(
            index=3,
            email="heynemann@gmail.com",
            first_name="Tom",
            last_name="Doe",
            embedded=EmbeddedDocument(test="test3"),
            nullable=EmbeddedDocument(test="test3"),
            numbers=[7, 8, 9],
        )

        cat1 = yield from Category.objects.create(name="category1", descr="category1 description")

        post1 = yield from Post.objects.create(
            title="post1 title",
            text="post1 text",
            category=cat1,
            comments=[
                Comment(title="comment1", text="comment1 text"),
                Comment(title="comment2", text="comment2 text"),
                Comment(title="comment3", text="comment3 text"),
            ],
        )

        self.user.posts.append(post1)
        yield from self.user.save()

    @async_test
    @asyncio.coroutine
    def test_can_project_with_only(self):
        users = yield from User.objects.filter(last_name="Else").only(User.first_name).order_by(User.index).find_all()

        expect(users).to_length(1)
        expect(users[0].first_name).to_equal("Someone")
        expect(users[0].last_name).to_equal("Heynemann")  # defaul value
        expect(users[0].email).to_be_null()

        users = yield from User.objects.filter(last_name="Else").only("first_name").order_by(User.index).find_all()

        expect(users).to_length(1)
        expect(users[0].first_name).to_equal("Someone")
        expect(users[0].last_name).to_equal("Heynemann")  # defaul value
        expect(users[0].email).to_be_null()

    @async_test
    @asyncio.coroutine
    def test_can_project_with_onlies_chain(self):
        user = yield from User.objects.only("first_name", "embedded.test").only("last_name").get(first_name="Someone")

        expect(user).not_to_be_null()
        expect(user._id).not_to_be_null()  # _id is still present
        expect(user.email).to_be_null()
        expect(user.first_name).to_equal("Someone")
        expect(user.last_name).to_equal("Else")
        expect(user.embedded.test).to_equal("test2")

    @async_test
    @asyncio.coroutine
    def test_can_project_with_exclude(self):
        user = yield from User.objects.exclude("first_name").get(first_name="Someone")

        expect(user).not_to_be_null()
        expect(user._id).not_to_be_null()
        expect(user.email).to_equal("heynemann@gmail.com")
        expect(user.first_name).to_equal("Bernardo")  # default value
        expect(user.last_name).to_equal("Else")
        expect(user.embedded.test).to_equal("test2")

        user = yield from User.objects.exclude(User.first_name).get(first_name="Someone")

        expect(user).not_to_be_null()
        expect(user._id).not_to_be_null()
        expect(user.email).to_equal("heynemann@gmail.com")
        expect(user.first_name).to_equal("Bernardo")  # default value
        expect(user.last_name).to_equal("Else")
        expect(user.embedded.test).to_equal("test2")

    @async_test
    @asyncio.coroutine
    def test_can_project_with_excludes_chain(self):
        users = (
            yield from User.objects.filter(last_name="Else")
            .exclude("_id")
            .exclude(User.email)
            .order_by(User.index)
            .find_all()
        )

        expect(users).to_length(1)
        expect(users[0]._id).to_be_null()
        expect(users[0].first_name).to_equal("Someone")
        expect(users[0].last_name).to_equal("Else")
        expect(users[0].email).to_be_null()
        expect(users[0].embedded.test).to_equal("test2")

    @async_test
    @asyncio.coroutine
    def test_can_combine_only_and_exclude(self):
        user = yield from User.objects.only("first_name").exclude("_id").get(last_name="Else")

        expect(user).not_to_be_null()
        expect(user._id).to_be_null()
        expect(user.first_name).to_equal("Someone")
        expect(user.email).to_be_null()
        expect(user.numbers).to_equal([])
        expect(user.last_name).to_equal("Heynemann")  # default value

        users = yield from User.objects.only("email", "numbers").exclude("numbers").order_by(User.index).find_all()

        expect(users[0].email).to_equal("heynemann@gmail.com")
        expect(users[0].numbers).to_equal([])

        users = yield from User.objects.exclude("numbers").only("email", "numbers").order_by(User.index).find_all()

        expect(users[0].email).to_equal("heynemann@gmail.com")
        expect(users[0].numbers).to_equal([])

    @async_test
    @asyncio.coroutine
    def test_can_project_embedded_fields(self):
        user = yield from User.objects.only("embedded.embedded2.test").get(last_name="Else")

        expect(user).not_to_be_null()
        expect(user._id).not_to_be_null()
        expect(user.last_name).to_equal("Heynemann")  # default value
        expect(user.first_name).to_equal("Bernardo")  # default value
        expect(user.embedded.embedded2.test).to_equal("test22")
        expect(user.embedded.test).to_be_null()

        user = yield from User.objects.exclude("embedded.test").exclude("email").get(last_name="Else")

        expect(user).not_to_be_null()
        expect(user._id).not_to_be_null()
        expect(user.last_name).to_equal("Else")
        expect(user.first_name).to_equal("Someone")
        expect(user.embedded.test).to_be_null()
        expect(user.email).to_be_null()

    @async_test
    @asyncio.coroutine
    def test_only_failed_with_wrong_field_name(self):
        with expect.error_to_happen(ValueError, message="Invalid field 'wrong': Field not found in 'User'."):
            yield from User.objects.only("wrong").get(last_name="Else")

        with expect.error_to_happen(
            ValueError, message=("Invalid field 'embedded.wrong': " "Field not found in 'User'.")
        ):
            yield from User.objects.only("embedded.wrong").get(last_name="Else")

    @async_test
    @asyncio.coroutine
    def test_exlude_failed_with_wrong_field_name(self):
        with expect.error_to_happen(ValueError, message="Invalid field 'wrong': Field not found in 'User'."):
            yield from User.objects.exclude("wrong").get(last_name="Else")

        with expect.error_to_happen(
            ValueError, message=("Invalid field 'embedded.wrong': " "Field not found in 'User'.")
        ):
            yield from User.objects.exclude("embedded.wrong").get(last_name="Else")

    @async_test
    @asyncio.coroutine
    def test_fields_failed_with_wrong_field_name(self):
        with expect.error_to_happen(ValueError, message="Invalid field 'wrong': Field not found in 'User'."):
            yield from User.objects.fields(wrong=QueryFieldList.ONLY).get(last_name="Else")

        with expect.error_to_happen(
            ValueError, message=("Invalid field 'embedded.wrong': " "Field not found in 'User'.")
        ):
            yield from User.objects.fields(embedded__wrong=QueryFieldList.EXCLUDE).get(last_name="Else")

        with expect.error_to_happen(
            ValueError, message=("Invalid field 'embedded.wrong': " "Field not found in 'User'.")
        ):
            yield from User.objects.fields(slice__embedded__wrong=10).get(last_name="Else")

    @async_test
    @asyncio.coroutine
    def test_can_slice_lists_in_projection(self):
        users = yield from User.objects.fields(slice__numbers=2).order_by(User.index).find_all()

        expect(users).to_length(3)
        expect(users[0].email).to_equal("heynemann@gmail.com")
        expect(users[0].numbers).to_length(2)
        expect(users[0].numbers).to_equal([1, 2])
        expect(users[1].numbers).to_equal([4, 5])

        users = yield from User.objects.fields(slice__numbers=(1, 2)).order_by(User.index).find_all()

        expect(users).to_length(3)
        expect(users[0].email).to_equal("heynemann@gmail.com")
        expect(users[0].numbers).to_length(2)
        expect(users[0].numbers).to_equal([2, 3])
        expect(users[1].numbers).to_equal([5, 6])

    @async_test
    @asyncio.coroutine
    def test_can_combine_slice_with_only_and_exlude(self):
        users = yield from User.objects.fields(slice__numbers=(1, 1)).only("email").order_by(User.index).find_all()

        expect(users[0].email).to_equal("heynemann@gmail.com")
        expect(users[0].numbers).to_equal([2])

        users = yield from User.objects.fields(slice__numbers=(1, 1)).exclude("numbers").order_by(User.index).find_all()

        expect(users[0].email).to_equal("heynemann@gmail.com")
        expect(users[0].numbers).to_equal([1, 2, 3])

        users = yield from User.objects.fields(slice__numbers=(1, 1)).only("_id").order_by(User.index).find_all()

        expect(users[0].email).to_be_null()
        expect(users[0]._id).not_to_be_null()
        expect(users[0].numbers).to_equal([2])

    @async_test
    @asyncio.coroutine
    def test_can_slice_lists_in_projection_with_negative_skip(self):
        users = yield from User.objects.fields(slice__numbers=-2).order_by(User.index).find_all()

        expect(users).to_length(3)
        expect(users[0].email).to_equal("heynemann@gmail.com")
        expect(users[0].numbers).to_length(2)
        expect(users[0].numbers).to_equal([2, 3])
        expect(users[1].numbers).to_equal([5, 6])
        expect(users[2].numbers).to_equal([8, 9])

        users = yield from User.objects.fields(slice__numbers=(-2, 1)).order_by(User.index).find_all()

        expect(users).to_length(3)
        expect(users[0].email).to_equal("heynemann@gmail.com")
        expect(users[0].numbers).to_length(1)
        expect(users[0].numbers).to_equal([2])
        expect(users[1].numbers).to_equal([5])
        expect(users[2].numbers).to_equal([8])

    @async_test
    @asyncio.coroutine
    def test_can_project_with_all_fields(self):
        user = yield from User.objects.only("last_name").exclude("_id").all_fields().get(last_name="Else")

        expect(user).not_to_be_null()
        expect(user._id).not_to_be_null()
        expect(user.email).to_equal("heynemann@gmail.com")
        expect(user.last_name).to_equal("Else")
        expect(user.first_name).to_equal("Someone")
        expect(user.numbers).to_equal([4, 5, 6])

    @async_test
    @asyncio.coroutine
    def test_can_project_list_of_embedded_documents(self):
        posts = yield from Post.objects.exclude("_id").only("comments.text").find_all()

        expect(posts).to_length(1)
        expect(posts[0]._id).to_be_null()
        expect(posts[0].title).to_be_null()
        expect(posts[0].text).to_be_null()
        expect(posts[0].category).to_be_null()
        expect(posts[0].comments).to_length(3)
        expect(posts[0].comments[0].text).to_equal("comment1 text")
        expect(posts[0].comments[0].title).to_be_null()
        expect(posts[0].comments[1].text).to_equal("comment2 text")
        expect(posts[0].comments[1].title).to_be_null()
        expect(posts[0].comments[2].text).to_equal("comment3 text")
        expect(posts[0].comments[2].title).to_be_null()

        # the same with fields
        posts = yield from Post.objects.fields(
            _id=QueryFieldList.EXCLUDE, comments__text=QueryFieldList.ONLY
        ).find_all()

        expect(posts).to_length(1)
        expect(posts[0]._id).to_be_null()
        expect(posts[0].title).to_be_null()
        expect(posts[0].text).to_be_null()
        expect(posts[0].category).to_be_null()
        expect(posts[0].comments).to_length(3)
        expect(posts[0].comments[0].text).to_equal("comment1 text")
        expect(posts[0].comments[0].title).to_be_null()
        expect(posts[0].comments[1].text).to_equal("comment2 text")
        expect(posts[0].comments[1].title).to_be_null()
        expect(posts[0].comments[2].text).to_equal("comment3 text")
        expect(posts[0].comments[2].title).to_be_null()

    @async_test
    @asyncio.coroutine
    def test_can_project_reference_field(self):
        posts = yield from Post.objects.only("title", "category.name").find_all(lazy=False)

        expect(posts).to_length(1)
        expect(posts[0].title).to_equal("post1 title")
        expect(posts[0].comments).to_length(0)
        expect(posts[0].text).to_be_null()
        expect(posts[0].category).to_be_instance_of(Category)
        expect(posts[0].category.name).to_equal("category1")
        expect(posts[0].category.descr).to_be_null()

        # the same with load_references
        posts = yield from Post.objects.only("title", "category.name").find_all(lazy=True)

        expect(posts).to_length(1)
        expect(posts[0].title).to_equal("post1 title")
        expect(posts[0].comments).to_length(0)
        expect(posts[0].text).to_be_null()

        with expect.error_to_happen(LoadReferencesRequiredError):
            cat = posts[0].category

        yield from posts[0].load_references()

        expect(posts[0].category).to_be_instance_of(Category)
        expect(posts[0].category.name).to_equal("category1")
        expect(posts[0].category.descr).to_be_null()

    @async_test
    @asyncio.coroutine
    def test_can_project_list_of_references(self):
        users = (
            yield from User.objects.only("first_name", "posts.title")
            .exclude("posts._id")
            .order_by(User.first_name)
            .find_all(lazy=False)
        )

        expect(users).to_length(3)
        expect(users[0].email).to_be_null()
        expect(users[1].email).to_be_null()
        expect(users[2].email).to_be_null()
        expect(users[0].first_name).to_equal("Bernardo")
        expect(users[1].first_name).to_equal("Someone")
        expect(users[2].first_name).to_equal("Tom")
        expect(users[0].last_name).to_equal("Heynemann")
        expect(users[1].last_name).to_equal("Heynemann")
        expect(users[2].last_name).to_equal("Heynemann")
        expect(users[0].posts).to_length(1)
        expect(users[1].posts).to_length(0)
        expect(users[2].posts).to_length(0)
        expect(users[0].posts[0]).to_be_instance_of(Post)
        expect(users[0].posts[0].title).to_equal("post1 title")
        expect(users[0].posts[0].text).to_be_null()
        expect(users[0].posts[0]._id).to_be_null()

    @async_test
    @asyncio.coroutine
    def test_document_is_partly_loaded(self):
        only_users = yield from User.objects.only("first_name").order_by(User.index).find_all()

        expect(only_users[0].is_partly_loaded).to_be_true()
        expect(only_users[1].is_partly_loaded).to_be_true()
        expect(only_users[2].is_partly_loaded).to_be_true()

        exclude_users = yield from User.objects.exclude("first_name").order_by(User.index).find_all()

        expect(exclude_users[0].is_partly_loaded).to_be_true()
        expect(exclude_users[1].is_partly_loaded).to_be_true()
        expect(exclude_users[2].is_partly_loaded).to_be_true()

        slice_users = yield from User.objects.fields(slice__numbers=2).order_by(User.index).find_all()

        expect(slice_users[0].is_partly_loaded).to_be_true()
        expect(slice_users[1].is_partly_loaded).to_be_true()
        expect(slice_users[2].is_partly_loaded).to_be_true()

    @async_test
    @asyncio.coroutine
    def test_document_is_not_partly_loaded(self):
        users = yield from User.objects.order_by(User.index).find_all()

        expect(users[0].is_partly_loaded).not_to_be_true()
        expect(users[1].is_partly_loaded).not_to_be_true()
        expect(users[2].is_partly_loaded).not_to_be_true()

        all_fields_users = (
            yield from User.objects.only("first_name").exclude("_id").all_fields().order_by(User.index).find_all()
        )

        expect(all_fields_users[0].is_partly_loaded).not_to_be_true()
        expect(all_fields_users[1].is_partly_loaded).not_to_be_true()
        expect(all_fields_users[2].is_partly_loaded).not_to_be_true()

    @async_test
    @asyncio.coroutine
    def test_document_failed_to_save_partly_loaded_document(self):
        user = yield from User.objects.only("first_name").get(first_name="Someone")

        with expect.error_to_happen(
            PartlyLoadedDocumentError,
            message=(
                "Partly loaded document User can't be saved. Document should "
                "be loaded without 'only', 'exclude' or 'fields' "
                "QuerySet's modifiers"
            ),
        ):
            yield from user.save()

    @async_test
    @asyncio.coroutine
    def test_queryset_failed_to_save_partly_loaded_document(self):
        users = yield from User.objects.only("first_name").filter(first_name="Someone").order_by(User.index).find_all()

        expect(users).to_length(1)

        with expect.error_to_happen(
            PartlyLoadedDocumentError,
            message=(
                "Partly loaded document User can't be saved. Document should "
                "be loaded without 'only', 'exclude' or 'fields' "
                "QuerySet's modifiers"
            ),
        ):
            yield from User.objects.save(users[0])
