package com.example.rag.common;

public class BusinessException extends RuntimeException {

    private final Integer code;

    public BusinessException(ErrorCode errorCode) {
        super(errorCode.getMsg());
        this.code = errorCode.getCode();
    }

    public BusinessException(ErrorCode errorCode, String msg) {
        super(msg);
        this.code = errorCode.getCode();
    }

    public Integer getCode() {
        return code;
    }
}
