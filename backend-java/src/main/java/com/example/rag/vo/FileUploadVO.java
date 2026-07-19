package com.example.rag.vo;

public class FileUploadVO {

    private Long fileId;
    private String fileName;
    private String status;

    public FileUploadVO() {
    }

    public FileUploadVO(Long fileId, String fileName, String status) {
        this.fileId = fileId;
        this.fileName = fileName;
        this.status = status;
    }

    public Long getFileId() {
        return fileId;
    }

    public void setFileId(Long fileId) {
        this.fileId = fileId;
    }

    public String getFileName() {
        return fileName;
    }

    public void setFileName(String fileName) {
        this.fileName = fileName;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }
}
