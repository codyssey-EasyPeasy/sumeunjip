"""시험용 공유 토큰(합성 값). conftest 가 이 값을 임시 토큰 파일에 써서 GPU_TOKEN_FILE 로 넘긴다."""

TEST_TOKEN = "test-token-0123456789abcdef"
AUTH = {"X-Internal-Token": TEST_TOKEN}
