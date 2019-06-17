from preggy import expect

from jetengine.query.greater_than import GreaterThanQueryOperator
from jetengine.query.not_operator import NotOperator
from tests import AsyncTestCase


class TestNotQueryOperator(AsyncTestCase):
    def test_to_query(self):
        query = NotOperator()
        expect(query).not_to_be_null()

        expect(query.to_query("field_name", GreaterThanQueryOperator(), 10)).to_be_like(
            {"field_name": {"$not": {"$gt": 10}}}
        )
