import os
import re

import arrow
from datetime import datetime
from gql import Client as Memberful, gql
from gql.transport.requests import RequestsHTTPTransport

from juniorguru.lib import loggers
from juniorguru.sync import subscriptions, companies
from juniorguru.lib.tasks import sync_task
from juniorguru.models import db, Company


logger = loggers.get(__name__)


MEMBERFUL_API_KEY = os.environ['MEMBERFUL_API_KEY']

MEMBERFUL_MUTATIONS_ENABLED = bool(int(os.getenv('MEMBERFUL_MUTATIONS_ENABLED', 0)))


@sync_task(subscriptions.main, companies.main)
@db.connection_context()
def main():
    # https://memberful.com/help/integrate/advanced/memberful-api/
    # https://juniorguru.memberful.com/api/graphql/explorer?api_user_id=52463
    transport = RequestsHTTPTransport(url='https://juniorguru.memberful.com/api/graphql/',
                                      headers={'Authorization': f'Bearer {MEMBERFUL_API_KEY}'},
                                      verify=True, retries=3)
    memberful = Memberful(transport=transport)
    mutation = gql('''
        mutation ($id: ID!, $expiresAt: Int!) {
            subscriptionChangeExpirationTime(id: $id, expiresAt: $expiresAt) {
                subscription {
                    id
                    expiresAt
                }
            }
        }
    ''')

    paying_companies = (company for company in Company.listing()
                        if company.expires_on)
    for company in paying_companies:
        logger_c = logger.getChild(re.sub('\W', '', company.name).lower())
        logger_c.info(f'Company subscription expires on {company.expires_on}')
        for employee in company.list_employees:
            logger_c.debug(f'Processing {employee.display_name}')
            if employee.expires_at.date() < company.expires_on:
                logger_c.warning(f'{employee!r} {employee.expires_at.date()} < {company.expires_on}')
                if MEMBERFUL_MUTATIONS_ENABLED:
                    params = dict(id=employee.subscription_id,
                                expiresAt=int(arrow.get(company.expires_on).timestamp()))
                    memberful.execute(mutation, variable_values=params)
                    employee.expires_at = datetime.combine(company.expires_on, datetime.min.time())
                    employee.save()
                    logger_c.info(f'{employee!r} subscription updated to expire on {employee.expires_at.date()}')
                else:
                    logger_c.warning('Memberful mutations not enabled')
            else:
                logger_c.debug(f'{employee!r} {employee.expires_at.date()} ≥ {company.expires_on}')