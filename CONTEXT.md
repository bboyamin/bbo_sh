# LocalIssueNotifier Context

지역 이슈 수집 및 실시간 맞춤 알림을 제공하는 팩트챗 내 서브 시스템의 도메인 용어집입니다.

## Language

**IssueItem**:
네이버 뉴스/블로그, 구글 RSS, 글로벌 소스(YouTube, Threads) 등 다양한 채널에서 수집된 단일 지역 소식 항목입니다.
_Avoid_: 피드, 글, 아티클, 게시글

**IssueCluster**:
동일하거나 매우 유사한 주제를 다루는 복수의 IssueItem이 제목 유사도와 수집 시점을 기반으로 묶인 도메인 그룹입니다.
_Avoid_: 토픽그룹, 뉴스모음, 이원화이슈

**DeduplicationEngine**:
수집된 IssueItem들 중 정규화된 URL 및 제목 문자열 유사도를 분석하여 중복 콘텐츠를 필터링하는 도메인 구성 요소입니다.
_Avoid_: 중복제거기, 정형화필터

**UserKeywordContext**:
사용자가 지정한 지역 및 관심 키워드 셋(예: 용인시, 처인구, 경전철 등)으로 이슈 수집 대상 범위를 결정하는 정보입니다.
_Avoid_: 필터목록, 태그목록, 사용자설정

**TokenSaverCache**:
수집 요청 시 1시간 이내에 수집 완료된 키워드 및 데이터를 캐싱하여 외부 API 호출 및 팩트챗 토큰 사용량을 최적화하는 저장소입니다.
_Avoid_: 웹캐시, 일시저장소

**OnDemandSummary**:
사용자가 특정 IssueItem 또는 IssueCluster에 대해 상세 요약을 요청했을 때 FactChat Gateway AI를 통해 동적으로 생성하는 AI 분석 리포트입니다.
_Avoid_: AI요약, 자동요약, 요약본
