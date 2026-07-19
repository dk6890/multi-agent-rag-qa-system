package com.example.rag;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@MapperScan("com.example.rag.mapper")
@ConfigurationPropertiesScan
public class RagQaApplication {

    public static void main(String[] args) {
        SpringApplication.run(RagQaApplication.class, args);
    }
}
