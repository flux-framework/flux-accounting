#!/bin/bash

test_description='test flux-account commands that deal with projects'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/flux_account

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1 &&
	flux account add-bank --parent-bank=root D 1 &&
	flux account add-bank --parent-bank=D E 1
	flux account add-bank --parent-bank=D F 1
'

test_expect_success 'add some users to the DB' '
	flux account add-user --username=user5011 --userid=5011 --bank=A &&
	flux account add-user --username=user5012 --userid=5012 --bank=A &&
	flux account add-user --username=user5013 --userid=5013 --bank=B &&
	flux account add-user --username=user5014 --userid=5014 --bank=C
'

test_expect_success 'add some queues to the DB' '
	flux account add-queue standby --priority=0 &&
	flux account add-queue expedite --priority=10000 &&
	flux account add-queue special --priority=99999
'

test_expect_success 'list contents of project_table before adding projects' '
	flux account list-projects > project_table.test &&
	cat <<-EOF >project_table.expected
	project_id | project | usage
	-----------+---------+------
	1          | *       | 0.0
	EOF
	grep -f project_table.expected project_table.test
'

test_expect_success 'add some projects to the project_table' '
	flux account add-project project_1 &&
	flux account add-project project_2 &&
	flux account add-project project_3 &&
	flux account add-project project_4
'

test_expect_success 'view project information from the project_table' '
	flux account view-project project_1 > project_1.out &&
	grep -w "1\|project_1" project_1.out
'

test_expect_success 'add a user with some specified projects to the association_table' '
	flux account add-user --username=user5015 --bank=A --projects="project_1,project_3" &&
	flux account view-user user5015 > user5015_info.out &&
	grep "\"username\": \"user5015\"" user5015_info.out &&
	grep ""project_1,project_3,*"" user5015_info.out
'

test_expect_success 'adding a user with a non-existing project should fail' '
	test_must_fail flux account add-user --username=user5016 --bank=A --projects="project_1,foo" > bad_project.out 2>&1 &&
	grep "project foo does not exist in project_table" bad_project.out
'

test_expect_success 'successfully edit a projects list for a user' '
	flux account edit-user user5015 --bank=A --projects="project_1,project_2,project_3" &&
	flux account view-user user5015 > user5015_edited_info.out &&
	grep "\"username\": \"user5015\"" user5015_edited_info.out &&
	grep "project_1,project_2,project_3,*" user5015_edited_info.out
'

test_expect_success 'editing a user project list with a non-existing project should fail' '
	test_must_fail flux account edit-user user5015 --bank=A --projects="project_1,foo" > bad_project_2.out 2>&1 &&
	grep "project foo does not exist in project_table" bad_project_2.out
'

test_expect_success 'remove a project from the project_table that is still referenced by at least one user' '
	flux account delete-project project_1 > warning_message.out &&
	test_must_fail flux account view-project project_1 > deleted_project.out 2>&1 &&
	grep "WARNING: user(s) in the association_table still reference this project." warning_message.out &&
	grep "project project_1 not found in project_table" deleted_project.out
'

test_expect_success 'remove a project that is not referenced by any users' '
	flux account delete-project project_4 &&
	test_must_fail flux account view-project project_4 > deleted_project_2.out 2>&1 &&
	grep "project project_4 not found in project_table" deleted_project_2.out
'

test_expect_success 'add a user to the accounting DB without specifying any projects' '
	flux account add-user --username=user5017 --bank=A &&
	flux account view-user user5017 > default_project_unspecified.test &&
	cat <<-EOF >default_project_unspecfied.expected
	default_project
	*
	EOF
	grep -f default_project_unspecfied.expected default_project_unspecified.test
'

test_expect_success 'add a user to the accounting DB and specify a project' '
	flux account add-user --username=user5018 --bank=A --projects=project_2 &&
	flux account view-user user5018 > default_project_specified.test &&
	cat <<-EOF >default_project_specified.expected
	default_project
	project_2
	EOF
	grep -f default_project_specified.expected default_project_specified.test
'

test_expect_success 'edit the default project of a user' '
	flux account edit-user user5018 --default-project=* &&
	flux account view-user user5018 > edited_default_project.test &&
	cat <<-EOF >edited_default_project.expected
	default_project
	*
	EOF
	grep -f edited_default_project.expected edited_default_project.test
	cat <<-EOF >projects_list.expected
	projects
	project_2,*
	EOF
	grep -f projects_list.expected edited_default_project.test
'

test_expect_success 'reset the projects list for an association' '
	flux account edit-user user5018 --projects=-1 &&
	flux account view-user user5018 --json > user5018.json &&
	grep "\"projects\": \"*\"" user5018.json
'

test_expect_success 'list all of the projects currently registered in project_table' '
	flux account list-projects > project_table.test &&
	cat <<-EOF >project_table.expected
	project_id | project   | usage
	-----------+-----------+------
	1          | *         | 0.0
	3          | project_2 | 0.0
	4          | project_3 | 0.0
	EOF
	grep -f project_table.expected project_table.test
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
