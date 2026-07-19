package com.example.rag.controller;

import com.example.rag.common.ApiResponse;
import com.example.rag.service.FileService;
import com.example.rag.vo.FileListVO;
import com.example.rag.vo.FileUploadVO;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/files")
public class FileController {

    private final FileService fileService;

    public FileController(FileService fileService) {
        this.fileService = fileService;
    }

    @PostMapping("/upload")
    public ApiResponse<FileUploadVO> upload(@RequestParam("file") MultipartFile file) {
        return ApiResponse.success("上传成功", fileService.upload(file));
    }

    @GetMapping("/list")
    public ApiResponse<List<FileListVO>> listFiles() {
        return ApiResponse.success(fileService.listFiles());
    }
}
