#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Docker 이미지 빌드 시 서비스 참조 데이터를 미리 캐싱하는 스크립트.

빌드 환경(인터넷 가능)에서 실행되어 외부 URL의 응답을 로컬 캐시 파일로 저장한다.
이후 폐쇄망 런타임에서는 이 캐시 파일을 사용한다.
"""

import json
import os
import requests
import sys
from pathlib import Path

SERVICE_REFERENCE_URL = 'https://servicereference.us-east-1.amazonaws.com/'
REQUEST_TIMEOUT = 10


def main():
    cache_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/app/cache')
    operations_dir = cache_dir / 'service_operations'
    cache_dir.mkdir(parents=True, exist_ok=True)
    operations_dir.mkdir(parents=True, exist_ok=True)

    # 1. 서비스 참조 URL 목록 가져오기
    print(f'Fetching service reference from {SERVICE_REFERENCE_URL} ...')
    try:
        response = requests.get(SERVICE_REFERENCE_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        service_list = response.json()
    except Exception as e:
        print(f'ERROR: Failed to fetch service reference: {e}', file=sys.stderr)
        sys.exit(1)

    ref_file = cache_dir / 'service_reference_urls.json'
    with open(ref_file, 'w') as f:
        json.dump(service_list, f)
    print(f'Cached {len(service_list)} service references -> {ref_file}')

    # 2. 각 서비스별 읽기 전용 작업 목록 가져오기
    success = 0
    failed = 0
    for svc in service_list:
        service_name = svc['service']
        service_url = svc['url']
        try:
            svc_resp = requests.get(service_url, timeout=REQUEST_TIMEOUT)
            svc_resp.raise_for_status()
            svc_data = svc_resp.json()
            read_only_ops = [
                action['Name']
                for action in svc_data.get('Actions', [])
                if not action.get('Annotations', {}).get('Properties', {}).get('IsWrite', True)
            ]
            svc_file = operations_dir / f'{service_name}.json'
            with open(svc_file, 'w') as f:
                json.dump(read_only_ops, f)
            success += 1
        except Exception as e:
            print(f'  WARNING: Failed to cache {service_name}: {e}', file=sys.stderr)
            failed += 1

    print(f'Done: {success} services cached, {failed} failed')


if __name__ == '__main__':
    main()
