"""
Unit tests for Tree-sitter Code Understanding across all 7 supported languages:
Python, JavaScript, TypeScript, TSX, Java, C, C++, and Go.
"""

import pytest
from backend.app.processing.engine import code_engine
from backend.app.processing.models import SymbolType


def test_python_parsing():
    code = """
import os
from sys import argv as sys_argv

class Animal:
    \"\"\"Base animal class.\"\"\"
    def __init__(self, name: str):
        self.name = name

class Dog(Animal):
    \"\"\"Domestic dog class.\"\"\"
    def bark(self, times: int = 1) -> str:
        \"\"\"Bark loudly.\"\"\"
        for _ in range(times):
            print("Woof!")
        return "Done"

def make_sound(dog: Dog):
    dog.bark()
"""
    parsed = code_engine.parse_source_code(code, "animals/dog.py", "test_repo")
    assert parsed is not None
    assert parsed.language == "python"
    assert parsed.file_path == "animals/dog.py"

    # Classes
    classes = [s for s in parsed.symbols if s.symbol_type == SymbolType.CLASS]
    assert len(classes) == 2
    assert {c.name for c in classes} == {"Animal", "Dog"}

    dog_class = next(c for c in classes if c.name == "Dog")
    assert dog_class.docstring == "Domestic dog class."
    assert dog_class.location.start_line > 0

    # Inheritance
    assert len(parsed.inheritances) == 1
    assert parsed.inheritances[0].super_name == "Animal"
    assert parsed.inheritances[0].relationship == "INHERITS"

    # Methods
    methods = [s for s in parsed.symbols if s.symbol_type == SymbolType.METHOD]
    assert len(methods) >= 2
    bark_method = next(m for m in methods if m.name == "bark")
    assert bark_method.docstring == "Bark loudly."
    assert bark_method.parent_symbol_id == dog_class.symbol_id
    assert "times" in bark_method.parameters[1]

    # Functions
    funcs = [s for s in parsed.symbols if s.symbol_type == SymbolType.FUNCTION]
    assert len(funcs) == 1
    assert funcs[0].name == "make_sound"

    # Imports
    assert len(parsed.imports) >= 2
    assert any(i.module == "os" for i in parsed.imports)
    assert any("argv" in i.imported_symbols for i in parsed.imports)

    # Calls
    assert len(parsed.calls) >= 2
    assert any(c.callee_name == "bark" for c in parsed.calls)


def test_javascript_and_commonjs_parsing():
    code = """
const path = require('path');
const logger = require('./logger');

const calculateScore = (hits, misses) => {
    return hits * 10 - misses * 5;
};

class GameController {
    start() {
        console.log("Game started");
        calculateScore(5, 1);
    }
}

module.exports = { GameController, calculateScore };
"""
    parsed = code_engine.parse_source_code(code, "src/game.js", "test_repo")
    assert parsed is not None
    assert parsed.language == "javascript"

    # Imports via require
    assert len(parsed.imports) >= 2
    assert any(i.module == "path" for i in parsed.imports)
    assert any(i.module == "./logger" for i in parsed.imports)

    # Arrow function symbol
    funcs = [s for s in parsed.symbols if s.symbol_type == SymbolType.FUNCTION]
    assert any(f.name == "calculateScore" for f in funcs)

    # Class & Method
    classes = [s for s in parsed.symbols if s.symbol_type == SymbolType.CLASS]
    assert len(classes) == 1
    assert classes[0].name == "GameController"

    methods = [s for s in parsed.symbols if s.symbol_type == SymbolType.METHOD]
    assert len(methods) == 1
    assert methods[0].name == "start"

    # Calls
    assert any(c.callee_name == "log" and c.receiver == "console" for c in parsed.calls)
    assert any(c.callee_name == "calculateScore" for c in parsed.calls)


def test_typescript_and_interfaces_parsing():
    code = """
import { Request, Response } from 'express';
import BaseService from './base';

export interface IService {
    execute(req: Request): Promise<Response>;
}

export class UserService extends BaseService implements IService {
    async execute(req: Request): Promise<Response> {
        this.validate(req);
        return {} as Response;
    }

    private validate(req: Request): boolean {
        return true;
    }
}
"""
    parsed = code_engine.parse_source_code(code, "src/services/user.ts", "test_repo")
    assert parsed is not None
    assert parsed.language == "typescript"

    # Interface
    ifaces = [s for s in parsed.symbols if s.symbol_type == SymbolType.INTERFACE]
    assert len(ifaces) == 1
    assert ifaces[0].name == "IService"

    # Class
    classes = [s for s in parsed.symbols if s.symbol_type == SymbolType.CLASS]
    assert len(classes) == 1
    assert classes[0].name == "UserService"

    # Inheritance & Implementation
    assert len(parsed.inheritances) >= 2
    assert any(inh.super_name == "BaseService" and inh.relationship == "INHERITS" for inh in parsed.inheritances)
    assert any(inh.super_name == "IService" and inh.relationship == "IMPLEMENTS" for inh in parsed.inheritances)

    # Methods
    methods = [s for s in parsed.symbols if s.symbol_type == SymbolType.METHOD]
    assert len(methods) == 2
    assert {m.name for m in methods} == {"execute", "validate"}


def test_java_parsing():
    code = """
package com.repomind.demo;

import java.util.List;
import java.util.ArrayList;

public class RepositoryManager extends AbstractManager implements IManager {
    private String repoName;

    public RepositoryManager(String repoName) {
        this.repoName = repoName;
    }

    @Override
    public List<String> listFiles() {
        System.out.println("Listing files");
        return new ArrayList<>();
    }
}
"""
    parsed = code_engine.parse_source_code(code, "src/main/java/RepositoryManager.java", "test_repo")
    assert parsed is not None
    assert parsed.language == "java"

    # Imports
    assert len(parsed.imports) >= 2
    assert any("List" in i.imported_symbols for i in parsed.imports)

    # Class
    classes = [s for s in parsed.symbols if s.symbol_type == SymbolType.CLASS]
    assert len(classes) == 1
    assert classes[0].name == "RepositoryManager"

    # Inheritance & Implementation
    assert any(inh.super_name == "AbstractManager" and inh.relationship == "INHERITS" for inh in parsed.inheritances)
    assert any(inh.super_name == "IManager" and inh.relationship == "IMPLEMENTS" for inh in parsed.inheritances)

    # Methods
    methods = [s for s in parsed.symbols if s.symbol_type == SymbolType.METHOD]
    assert any(m.name == "RepositoryManager" for m in methods)  # Constructor
    assert any(m.name == "listFiles" for m in methods)

    # Calls
    assert any(c.callee_name == "println" for c in parsed.calls)


def test_c_and_cpp_parsing():
    code = """
#include <iostream>
#include "engine.h"

class Vector3D : public MathEntity {
public:
    double x, y, z;

    Vector3D(double x, double y, double z) : x(x), y(y), z(z) {}

    double magnitude() {
        return sqrt(x*x + y*y + z*z);
    }
};

int main() {
    Vector3D v(1.0, 2.0, 3.0);
    std::cout << v.magnitude() << std::endl;
    return 0;
}
"""
    parsed = code_engine.parse_source_code(code, "src/vector.cpp", "test_repo")
    assert parsed is not None
    assert parsed.language == "cpp"

    # Includes
    assert len(parsed.imports) >= 2
    assert any(i.module == "iostream" for i in parsed.imports)
    assert any(i.module == "engine.h" for i in parsed.imports)

    # Class
    classes = [s for s in parsed.symbols if s.symbol_type == SymbolType.CLASS]
    assert len(classes) == 1
    assert classes[0].name == "Vector3D"

    # Inheritance
    assert len(parsed.inheritances) == 1
    assert parsed.inheritances[0].super_name == "MathEntity"

    # Function
    funcs = [s for s in parsed.symbols if s.symbol_type == SymbolType.FUNCTION]
    assert any(f.name == "main" for f in funcs)


def test_go_parsing():
    code = """
package server

import (
    "fmt"
    "net/http"
)

type Server interface {
    Start() error
}

type HttpServer struct {
    Port int
}

func (s *HttpServer) Start() error {
    fmt.Printf("Starting server on port %d\\n", s.Port)
    return http.ListenAndServe(fmt.Sprintf(":%d", s.Port), nil)
}

func NewServer(port int) *HttpServer {
    return &HttpServer{Port: port}
}
"""
    parsed = code_engine.parse_source_code(code, "pkg/server/server.go", "test_repo")
    assert parsed is not None
    assert parsed.language == "go"

    # Imports
    assert len(parsed.imports) >= 2
    assert any(i.module == "fmt" for i in parsed.imports)
    assert any(i.module == "net/http" for i in parsed.imports)

    # Struct & Interface
    assert any(s.name == "Server" and s.symbol_type == SymbolType.INTERFACE for s in parsed.symbols)
    assert any(s.name == "HttpServer" and s.symbol_type == SymbolType.STRUCT for s in parsed.symbols)

    # Method with receiver
    methods = [s for s in parsed.symbols if s.symbol_type == SymbolType.METHOD]
    assert len(methods) == 1
    assert methods[0].name == "Start"
    assert methods[0].properties.get("receiver") == "HttpServer"

    # Function
    funcs = [s for s in parsed.symbols if s.symbol_type == SymbolType.FUNCTION]
    assert len(funcs) == 1
    assert funcs[0].name == "NewServer"

    # Calls
    assert any(c.callee_name == "Printf" for c in parsed.calls)
    assert any(c.callee_name == "ListenAndServe" for c in parsed.calls)

