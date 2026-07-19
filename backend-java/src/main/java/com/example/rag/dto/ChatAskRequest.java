package com.example.rag.dto;

import jakarta.validation.constraints.NotBlank;

public class ChatAskRequest {

    @NotBlank(message = "问题不能为空")
    private String question;
    private Long sessionId;

    public String getQuestion() {
        return question;
    }

    public void setQuestion(String question) {
        this.question = question;
    }

    public Long getSessionId() {
        return sessionId;
    }

    public void setSessionId(Long sessionId) {
        this.sessionId = sessionId;
    }
}
