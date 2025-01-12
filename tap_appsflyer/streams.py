import singer
from .transform import *
from datetime import datetime, timedelta, timezone

LOGGER = singer.get_logger()

raw_reports_api_max_window = 90 #days
raw_client_date_fmt = '%Y-%m-%d %H:%M'

daily_reports_api_max_window = 1000 #days
daily_client_date_fmt = '%Y-%m-%d'


# This order matters
RAW_INSTALL_N_IN_APP_FIELDNAMES = (
    "attributed_touch_type",
    "attributed_touch_time",
    "install_time",
    "event_time",
    "event_name",
    "event_value",
    "event_revenue",
    "event_revenue_currency",
    "event_revenue_usd",
    "event_source",
    "is_receipt_validated",
    "af_prt",
    "media_source",
    "af_channel",
    "af_keywords",
    "campaign",
    "af_c_id",
    "af_adset",
    "af_adset_id",
    "af_ad",
    "af_ad_id",
    "af_ad_type",
    "af_siteid",
    "af_sub_siteid",
    "af_sub1",
    "af_sub2",
    "af_sub3",
    "af_sub4",
    "af_sub5",
    "af_cost_model",
    "af_cost_value",
    "af_cost_currency",
    "contributor1_af_prt",
    "contributor1_media_source",
    "contributor1_campaign",
    "contributor1_touch_type",
    "contributor1_touch_time",
    "contributor2_af_prt",
    "contributor2_media_source",
    "contributor2_campaign",
    "contributor2_touch_type",
    "contributor2_touch_time",
    "contributor3_af_prt",
    "contributor3_media_source",
    "contributor3_campaign",
    "contributor3_touch_type",
    "contributor3_touch_time",
    "region",
    "country_code",
    "state",
    "city",
    "postal_code",
    "dma",
    "ip",
    "wifi",
    "operator",
    "carrier",
    "language",
    "appsflyer_id",
    "advertising_id",
    "idfa",
    "android_id",
    "customer_user_id",
    "imei",
    "idfv",
    "platform",
    "device_type",
    "os_version",
    "app_version",
    "sdk_version",
    "app_id",
    "app_name",
    "bundle_id",
    "is_retargeting",
    "retargeting_conversion_type",
    "af_attribution_lookback",
    "af_reengagement_window",
    "is_primary_attribution",
    "user_agent",
    "http_referrer",
    "original_url",
)


PARTNERS_FIELDNAMES = (
    "date",
    "agency",
    "media_source",
    "campaign",
    "impressions",
    "clicks",
    "ctr",
    "installs",
    "conversion_rate",
    "sessions",
    "loyal_users",
    "loyal_users_installs",
    "total_revenue",
    "total_cost",
    "roi",
    "arpu",
    "average_ecpi",
)


class Stream:
    bookmark_date_format = '%Y-%m-%dT%H:%MZ'
    reports_api_max_window = None
    fieldnames = None
    client_date_fmt = None

    def __init__(self,client,config):
        self.client = client
        self.config = config


class RawData(Stream):
    reports_api_max_window = raw_reports_api_max_window
    client_date_fmt        = raw_client_date_fmt

    def _get_start_time(self,state,bookmark_format):
        # if start_date is in the config use it, if not, get 90 days ago
        if "start_date" in self.config:
            start_date = datetime.strptime(self.config["start_date"],self.bookmark_date_format)
        else:
            start_date = singer.utils.now().replace(hour=0,minute=0,second=0,microsecond=0) - timedelta(days=self.reports_api_max_window)

        # get bookmark
        start_time_str = singer.get_bookmark(
            state,
            self.tap_stream_id,
            self.replication_key,
            datetime.strftime(start_date,bookmark_format)
            )
        
        # add timezone UTC 0 without changing the date time
        start_time = datetime.strptime(start_time_str,bookmark_format).\
            replace(tzinfo=timezone.utc)
        
        return start_time
    
    def _get_end_time(self,bookmark_format):
        end_time = None
        if "end_date" in self.config:
            end_time = datetime.strptime(self.config["end_date"],self.bookmark_date_format).\
                replace(tzinfo=timezone.utc)
        else:
            end_time = singer.utils.now().replace(second=0,microsecond=0)
        
        return end_time


    """Defines the sync method for all raw data classes as the raw data endpoints have 
        the same structure."""
    def sync(self, state, stream_schema, stream_metadata, transformer):

        # Bookmark is in timezone UTC
        start_time = self._get_start_time(state,self.bookmark_date_format)
        end_time = self._get_end_time(self.bookmark_date_format)

        for record in self.client.get_data(
            self.report_name,
            self.report_version,
            start_time,
            end_time,     
            self.fieldnames,
            self.client_date_fmt):

            record = self.xform(record)

            transformed_record = transformer.transform(
                record,
                stream_schema,
                stream_metadata)
            singer.write_record(self.tap_stream_id,transformed_record,time_extracted=end_time)

        # Convert to bookmark format
        end_time_str = datetime.strftime(end_time,self.bookmark_date_format)
        state = singer.write_bookmark(state, self.tap_stream_id, self.replication_key, end_time_str)
        singer.write_state(state)

        return state
    
    def xform(self, record):
        return xform(record)


class DailyData(RawData):
    reports_api_max_window = daily_reports_api_max_window
    client_date_fmt        = daily_client_date_fmt
    
    def xform(self, record):
        return xform_agg(record)


class Installs(RawData):

    tap_stream_id = 'installs'
    key_properties = ["event_time","event_name","appsflyer_id"]
    replication_method = 'INCREMENTAL'
    valid_replication_keys = ['event_time']
    replication_key = 'event_time'
    report_name = 'installs_report'
    report_version = 'v5'
    fieldnames = RAW_INSTALL_N_IN_APP_FIELDNAMES


class InAppEvents(RawData):

    tap_stream_id = 'in_app_events'
    key_properties = ["event_time","event_name","appsflyer_id"]
    replication_method = 'INCREMENTAL'
    valid_replication_keys = ['date']
    replication_key = 'date'
    report_name = 'in_app_events_report'
    report_version = 'v5'
    fieldnames = RAW_INSTALL_N_IN_APP_FIELDNAMES


class PartnersByDate(DailyData):

    tap_stream_id = 'partners_by_date'
    key_properties = ["date","media_source","campaign"]
    replication_method = 'INCREMENTAL'
    valid_replication_keys = ['event_time']
    replication_key = 'event_time'
    report_name = 'partners_by_date_report'
    report_version = 'v5'
    fieldnames = PARTNERS_FIELDNAMES


STREAMS = {
    'installs': Installs,
    'in_app_events': InAppEvents,
    'partners_by_date': PartnersByDate
}