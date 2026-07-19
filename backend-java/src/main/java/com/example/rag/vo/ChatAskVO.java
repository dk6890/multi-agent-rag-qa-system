package com.example.rag.vo;

import java.util.ArrayList;
import java.util.List;

public class ChatAskVO {

    private Long sessionId;
    private String question;
    private String answer;
    private List<ReferenceVO> references = new ArrayList<>();

    public Long getSessionId() {
        return sessionId;
    }

    public void setSessionId(Long sessionId) {
        this.sessionId = sessionId;
    }

    public String getQuestion() {
        return question;
    }

    public void setQuestion(String question) {
        this.question = question;
    }

    public String getAnswer() {
        return answer;
    }

    public void setAnswer(String answer) {
        this.answer = answer;
    }

    public List<ReferenceVO> getReferences() {
        return references;
    }

    public void setReferences(List<ReferenceVO> references) {
        this.references = references;
    }
}
