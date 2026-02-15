# 定时任务 SOP

目录：`../tasks/{pending,running,done}/`
文件名：`YYYY-MM-DD_HHMM_描述.md`，内容含prompt和schedule

## 流程
1. [AUTO]唤醒 → `datetime.now()`取当前时间，`ls ../tasks/pending/`，文件名时间≤当前→到期，选择一个
2. **立即rename到running/**（先占再读，防多进程重复领）
3. 读文件执行
4. 完成→移到done/，**在文件内追加执行报告**供用户查阅
5. schedule非once→算下次时间，新建文件到pending/

注意tasks目录在../，即你的code root下
