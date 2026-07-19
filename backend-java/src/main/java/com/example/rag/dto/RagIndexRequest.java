package com.example.rag.dto;

public class RagIndexRequest {

    private Long fileId;
    private String filePath;
    private String fileName;

    public RagIndexRequest() {
    }

    public RagIndexRequest(Long fileId, String filePath, String fileName) {
        this.fileId = fileId;
        this.filePath = filePath;
        this.fileName = fileName;
    }

    public Long getFileId() {
        return fileId;
    }

    public void setFileId(Long fileId) {
        this.fileId = fileId;
    }

    public String getFilePath() {
        return filePath;
    }

    public void setFilePath(String filePath) {
        this.filePath = filePath;
    }

    public String getFileName() {
        return fileName;
    }

    public void setFileName(String fileName) {
        this.fileName = fileName;
    }
}
