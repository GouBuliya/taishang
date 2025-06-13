#!/bin/bash
# scripts/run_tests.sh
# 太熵量化交易系统测试运行脚本

set -e  # 遇到错误时退出

echo "🧪 太熵量化交易系统 - 测试运行脚本"
echo "=================================="

# 检查是否在项目根目录
if [ ! -f "pyproject.toml" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    exit 1
fi

# 创建测试报告目录
mkdir -p tests/reports

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函数：运行测试套件
run_test_suite() {
    local test_type=$1
    local test_path=$2
    local description=$3
    
    echo -e "\n${BLUE}📋 运行 ${description}...${NC}"
    echo "测试路径: $test_path"
    
    if uv run pytest "$test_path" -v --tb=short; then
        echo -e "${GREEN}✅ ${description} 通过${NC}"
        return 0
    else
        echo -e "${RED}❌ ${description} 失败${NC}"
        return 1
    fi
}

# 函数：运行带覆盖率的测试
run_coverage_test() {
    local test_path=$1
    local description=$2
    
    echo -e "\n${BLUE}📊 运行覆盖率测试: ${description}...${NC}"
    
    if uv run pytest "$test_path" \
        --cov=src \
        --cov-report=term-missing \
        --cov-report=html:tests/reports/coverage \
        --cov-report=xml:tests/reports/coverage.xml \
        --junitxml=tests/reports/junit.xml \
        -v; then
        echo -e "${GREEN}✅ 覆盖率测试完成${NC}"
        echo "📄 覆盖率报告: tests/reports/coverage/index.html"
        return 0
    else
        echo -e "${RED}❌ 覆盖率测试失败${NC}"
        return 1
    fi
}

# 主测试流程
main() {
    local failed_tests=0
    
    echo -e "\n${YELLOW}🚀 开始测试执行...${NC}"
    
    # 1. 运行快速单元测试
    echo -e "\n${BLUE}=== 第一阶段：快速单元测试 ===${NC}"
    
    if run_test_suite "unit" "tests/unit/core/" "核心模块单元测试"; then
        ((failed_tests+=0))
    else
        ((failed_tests+=1))
    fi
    
    if run_test_suite "unit" "tests/unit/data/" "数据模块单元测试"; then
        ((failed_tests+=0))
    else
        ((failed_tests+=1))
    fi
    
    if run_test_suite "unit" "tests/unit/ai/" "AI模块单元测试"; then
        ((failed_tests+=0))
    else
        ((failed_tests+=1))
    fi
    
    # 2. 运行集成测试（如果单元测试通过）
    if [ $failed_tests -eq 0 ]; then
        echo -e "\n${BLUE}=== 第二阶段：集成测试 ===${NC}"
        
        if [ -d "tests/integration" ]; then
            if run_test_suite "integration" "tests/integration/" "系统集成测试"; then
                ((failed_tests+=0))
            else
                ((failed_tests+=1))
            fi
        else
            echo -e "${YELLOW}⚠️  集成测试目录不存在，跳过集成测试${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  由于单元测试失败，跳过集成测试${NC}"
    fi
    
    # 3. 运行覆盖率测试
    echo -e "\n${BLUE}=== 第三阶段：代码覆盖率分析 ===${NC}"
    
    if run_coverage_test "tests/unit/" "单元测试覆盖率"; then
        ((failed_tests+=0))
    else
        ((failed_tests+=1))
    fi
    
    # 4. 性能测试（可选）
    echo -e "\n${BLUE}=== 第四阶段：性能测试 ===${NC}"
    
    echo -e "${BLUE}🚀 运行性能标记的测试...${NC}"
    if uv run pytest -m "performance" --tb=short -v; then
        echo -e "${GREEN}✅ 性能测试完成${NC}"
    else
        echo -e "${YELLOW}⚠️  性能测试有警告或失败${NC}"
    fi
    
    # 测试结果总结
    echo -e "\n${BLUE}=== 测试结果总结 ===${NC}"
    
    if [ $failed_tests -eq 0 ]; then
        echo -e "${GREEN}🎉 所有测试套件通过！${NC}"
        echo -e "${GREEN}✅ 系统测试完成，代码质量良好${NC}"
        
        # 显示覆盖率信息
        if [ -f "tests/reports/coverage.xml" ]; then
            echo -e "\n${BLUE}📊 测试覆盖率信息：${NC}"
            echo "📄 HTML报告: file://$(pwd)/tests/reports/coverage/index.html"
            echo "📄 XML报告:  tests/reports/coverage.xml"
            echo "📄 JUnit报告: tests/reports/junit.xml"
        fi
        
        exit 0
    else
        echo -e "${RED}❌ 有 $failed_tests 个测试套件失败${NC}"
        echo -e "${RED}🔧 请检查测试输出并修复相关问题${NC}"
        exit 1
    fi
}

# 处理命令行参数
case "${1:-}" in
    "unit")
        echo "🧪 只运行单元测试"
        run_test_suite "unit" "tests/unit/" "所有单元测试"
        ;;
    "integration")
        echo "🔗 只运行集成测试"
        run_test_suite "integration" "tests/integration/" "所有集成测试"
        ;;
    "coverage")
        echo "📊 只运行覆盖率测试"
        run_coverage_test "tests/unit/" "单元测试覆盖率"
        ;;
    "performance")
        echo "🚀 只运行性能测试"
        uv run pytest -m "performance" --tb=short -v
        ;;
    "fast")
        echo "⚡ 只运行快速测试"
        uv run pytest -m "fast" --tb=short -v
        ;;
    "slow")
        echo "🐌 只运行慢速测试"
        uv run pytest -m "slow" --tb=short -v
        ;;
    "help"|"-h"|"--help")
        echo "用法: $0 [选项]"
        echo ""
        echo "选项:"
        echo "  unit        只运行单元测试"
        echo "  integration 只运行集成测试"
        echo "  coverage    只运行覆盖率测试"
        echo "  performance 只运行性能测试"
        echo "  fast        只运行快速测试"
        echo "  slow        只运行慢速测试"
        echo "  help        显示此帮助信息"
        echo ""
        echo "无参数运行将执行完整的测试套件"
        ;;
    "")
        # 运行完整测试套件
        main
        ;;
    *)
        echo -e "${RED}❌ 未知选项: $1${NC}"
        echo "使用 '$0 help' 查看可用选项"
        exit 1
        ;;
esac 