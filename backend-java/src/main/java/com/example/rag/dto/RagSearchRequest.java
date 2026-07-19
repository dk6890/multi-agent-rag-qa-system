package com.example.rag.dto;

public class RagSearchRequest {

    private String question;
    private Integer topK;

    public RagSearchRequest() {
    }

    public RagSearchRequest(String question, Integer topK) {
        this.question = question;
        this.topK = topK;
    }

    public String getQuestion() {
        return question;
    }

    public void setQuestion(String question) {
        this.question = question;
    }

    public Integer getTopK() {
        return topK;
    }

    public void setTopK(Integer topK) {
        this.topK = topK;
    }
}
