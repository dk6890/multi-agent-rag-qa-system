package com.example.rag.service;

import com.example.rag.vo.FileListVO;
import com.example.rag.vo.FileUploadVO;
import java.util.List;
import org.springframework.web.multipart.MultipartFile;

public interface FileService {

    FileUploadVO upload(MultipartFile file);

    List<FileListVO> listFiles();
}
