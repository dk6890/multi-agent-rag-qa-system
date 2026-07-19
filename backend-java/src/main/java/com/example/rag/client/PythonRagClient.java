package com.example.rag.client;

import com.example.rag.common.ApiResponse;
import com.example.rag.common.BusinessException;
import com.example.rag.common.ErrorCode;
import com.example.rag.config.RagProperties;
import com.example.rag.dto.RagIndexRequest;
import com.example.rag.dto.RagIndexResponse;
import com.example.rag.dto.RagSearchRequest;
import com.example.rag.dto.RagSearchResponse;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpMethod;
import org.springframework.http.RequestEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

@Component
public class PythonRagClient {

    private final RestTemplate restTemplate;
    private final RagProperties properties;

    public PythonRagClient(RestTemplate restTemplate, RagProperties properties) {
        this.restTemplate = restTemplate;
        this.properties = properties;
    }

    public ApiResponse<RagIndexResponse> index(RagIndexRequest request) {
        String url = normalizeBaseUrl() + "/rag/index";
        try {
            RequestEntity<RagIndexRequest> entity = RequestEntity.post(url).body(request);
            return restTemplate.exchange(entity, new ParameterizedTypeReference<ApiResponse<RagIndexResponse>>() {
            }).getBody();
        } catch (RestClientException ex) {
            throw new BusinessException(ErrorCode.PYTHON_RAG_ERROR, "Python RAG 文件入库服务不可用: " + ex.getMessage());
        }
    }

    public ApiResponse<RagSearchResponse> search(RagSearchRequest request) {
        String url = normalizeBaseUrl() + "/rag/search";
        try {
            return restTemplate.exchange(
                    url,
                    HttpMethod.POST,
                    RequestEntity.post(url).body(request),
                    new ParameterizedTypeReference<ApiResponse<RagSearchResponse>>() {
                    }).getBody();
        } catch (RestClientException ex) {
            throw new BusinessException(ErrorCode.PYTHON_RAG_ERROR, "Python RAG 检索服务不可用: " + ex.getMessage());
        }
    }

    private String normalizeBaseUrl() {
        String serviceUrl = properties.getPython().getServiceUrl();
        if (serviceUrl.endsWith("/")) {
            return serviceUrl.substring(0, serviceUrl.length() - 1);
        }
        return serviceUrl;
    }
}
