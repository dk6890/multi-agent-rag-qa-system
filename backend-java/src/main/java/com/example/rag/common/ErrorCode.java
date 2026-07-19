package com.example.rag.common;

public enum ErrorCode {

    BAD_REQUEST(400, "请求参数错误"),
    NOT_FOUND(404, "资源不存在"),
    PYTHON_RAG_ERROR(500, "Python RAG 服务调用失败"),
    LLM_ERROR(500, "大模型服务调用失败"),
    INTERNAL_ERROR(500, "服务内部错误");

    private final Integer code;
    private final String msg;

    ErrorCode(Integer code, String msg) {
        this.code = code;
        this.msg = msg;
    }

    public Integer getCode() {
        return code;
    }

    public String getMsg() {
        return msg;
    }
}
