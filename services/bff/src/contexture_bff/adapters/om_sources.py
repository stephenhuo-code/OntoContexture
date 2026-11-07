"""005 源系统元数据采集：数据源、采集任务、运行、测试连接、目录与治理属性的 OM 适配（research R7–R9）。

全部经 OpenMetadata 公开 API、以登录用户的委托令牌调用（OmClient）；BFF 不连源库、不调 Airflow、不写运行状态，
不内置任何示例数据（宪法 v2.2.0）。实体映射见 specs/005-source-metadata-ingestion/data-model.md。
"""

from contexture_bff.adapters.om_client import OmClient


class SourcesService:
    def __init__(self, om: OmClient) -> None:
        self.om = om
