import os
import time
from sqlalchemy.schema import CreateTable
from flask import session, flash, request
from static.py.JMC_Func import string_to_bool as S2B
from static.py.JMC_Func import ClientResponses
from static.py.LogConf import log
import uuid
from sqlalchemy import inspect
import re
import traceback


sql_statements = {}

def get_rec_session_id():
    try:
        return session.setdefault('Rec_Session_Id', str(uuid.uuid4()))
    except Exception:
        log.error(traceback.format_exc())
        raise RuntimeError("An error occurred while getting the session ID")

def format_sql_statement(statement):
    try:
        return statement.replace('\n', ' ').replace('\t', ' ').strip() 
    except Exception:
        log.error(traceback.format_exc())
        raise RuntimeError("An error occurred while formatting the SQL statement")

def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    try:
        if session.get('recording') == True:
            log.debug(f'Recording for : {get_rec_session_id()}')
            if get_rec_session_id() not in sql_statements:
                sql_statements[get_rec_session_id()] = []
            sql_statements[get_rec_session_id()].append((statement, parameters))
    except Exception:
        log.error(traceback.format_exc())   
        raise RuntimeError("An error occurred while preparing the SQL statement for recording")

def GetCreateTableSql(db):
    try:
        table_create_statements = []
        for table in db.metadata.sorted_tables:
            create_statement = CreateTable(table)
            table_create_statements.append(format_sql_statement(str(create_statement.compile(db.engine))))
        if S2B(os.getenv('RecSQL')) == True:
            flash(str(table_create_statements).strip()[2:-2], 'info')
        log.debug(f'SQL Statement to Create all Tables: \n {str(table_create_statements).strip()[2:-2]}')
        return str(table_create_statements)
    except Exception:
        log.error(traceback.format_exc())
        raise RuntimeError("An error occurred while getting the SQL statement to create all tables")


def GetSqlQuery():
    try:
        formatted_sql_statements = []
        for statement, parameters in sql_statements[get_rec_session_id()]:
            formatted_statement = statement
            if isinstance(parameters, dict):
                for param_name, param_value in parameters.items():
                    placeholder = f'%({param_name})s'
                    if isinstance(param_value, str):
                        formatted_statement = formatted_statement.replace(placeholder, f"'{param_value}'")
                    else:
                        formatted_statement = formatted_statement.replace(placeholder, str(param_value))
            else:
                for param in parameters:
                    if isinstance(param, str):
                        formatted_statement = formatted_statement.replace('?', f"'{param}'", 1)
                    else:
                        formatted_statement = formatted_statement.replace('?', str(param), 1)
            formatted_sql_statements.append(format_sql_statement(formatted_statement))
        log.debug(f"Recorded SQL for: {get_rec_session_id()}\n{str(formatted_sql_statements).strip()[2:-2]}")      
        flash(str(formatted_sql_statements).strip()[2:-2], 'info')
        return formatted_sql_statements
    except Exception:
        log.error(traceback.format_exc())
        raise RuntimeError("An error occurred while getting the recorded SQL statements")

def StartSqlRec():
    try:
        session['recording'] = True
        sql_statements.pop(get_rec_session_id(), None) 
        log.debug(f'Recording started by: {get_rec_session_id()}')
        return f'Recording started by: {get_rec_session_id()}'
    except Exception:
        log.error(traceback.format_exc())
        raise RuntimeError("An error occurred while starting the SQL recording")

def StopSqlRec():
    try:
        session['recording'] = False
        log.debug(f'Recording stopped by: {get_rec_session_id()}')
        return f'Recording stopped by: {get_rec_session_id()}'
    except Exception:
        log.error(traceback.format_exc())
        raise RuntimeError("An error occurred while stopping the SQL recording")

def RecAndExe(func):
    try:
        StartSqlRec()
        result = func()
        GetSqlQuery()
        StopSqlRec()
        return result
    except Exception:
        log.error(traceback.format_exc())
        raise RuntimeError("An error occurred in the RecAndExe routine")
           

def Check(func,db,socketio,BaseModel):
    try:
        if (S2B(os.getenv('RecSQL')) == True or 
            S2B(os.getenv('NoCommit')) == True or
            session.get('use_in_memory_db') == True):
            StartSqlRec()
        Server_Result = func()
        if S2B(os.getenv('NoCommit')) or session.get('use_in_memory_db') == True:
            log.debug(f'flushing... for: {get_rec_session_id()}')
            db.session.flush()
        else:    
            log.debug(f'committing... for: {get_rec_session_id()}')
            if db.session.is_active:  
                db.session.commit() 
            with db.session.begin():  
                db.session.commit()
        if (S2B(os.getenv('RecSQL')) == True or
            S2B(os.getenv('NoCommit')) == True or
            session.get('use_in_memory_db') == True):
            SqlQuery = GetSqlQuery()
            if  session.get('use_in_memory_db') == True:
                room_id = request.cookies.get('room_id')
                response = None
                client_responses = ClientResponses()
                socketio.emit('json_data', {'sql': SqlQuery}, room=room_id)
                start_time = time.time()  
                timeout = 2  
                while time.time() - start_time < timeout:
                    response = client_responses.get_value(room_id)
                    if response is not None:
                        Client_Result = response.get('message')
                        if Client_Result == []:
                            Client_Result = None
                        else:
                            Client_Result = format_client_result_to_orm(Client_Result, SqlQuery, BaseModel)
                        client_responses.remove_value(room_id)
                        break
                    time.sleep(0.01) 
                if response is None:
                    log.error(f"{time.time()} - Response:: TimeOut - No data received")                
            StopSqlRec()  
        if  session.get('use_in_memory_db') == True:  
            result = Client_Result
        else:
            result = Server_Result      
        return result
    except Exception:
        log.error(traceback.format_exc())
        raise RuntimeError("An error occurred while checking what sql statements should be recorded and executed")


def format_client_result_to_orm(client_result, sql_query, BaseModel):
    try:
        table_names = extract_table_names(sql_query)
        orm_result = {table: [] for table in table_names}
        for table in table_names:
            model_class = get_model_by_table_name(table, BaseModel)
            if not model_class:
                raise ValueError(f"No model found for table: {table}")
            columns = inspect(model_class).columns.keys()
            for result in client_result:
                column_mapping = {client_col: model_col for client_col, model_col in zip(result['columns'], columns) if client_col.split('_', 1)[1] == model_col}
                if set(column_mapping.keys()).issubset(result['columns']):
                    table_data = [dict((column_mapping[col], row[col_index]) for col_index, col in enumerate(result['columns']) if col in column_mapping) for row in result.get('values', [])]
                    orm_result[table] = [dict_to_orm_instance(model_class, row) for row in table_data]
        if len(orm_result) == 1:
            first_table_results = list(orm_result.values())[0]
            if len(first_table_results) == 1:
                return first_table_results[0]
            return first_table_results
        return orm_result
    except Exception:
        log.error(traceback.format_exc())
        raise RuntimeError("An error occurred while formatting the client result to ORM")
    
def dict_to_orm_instance(model_class, row_dict):
    try:
        instance = model_class()
        for key, value in row_dict.items():
            if hasattr(model_class, key):
                setattr(instance, key, value)
        return instance
    except Exception as e:
        print(traceback.format_exc())
        raise RuntimeError("An error occurred while converting the dictionary to an ORM instance")

def extract_table_names(sql_query):
    try:
        if isinstance(sql_query, str):
            sql_query = [sql_query]
        table_names = []
        for query in sql_query:
            table_names += re.findall(r'FROM\s+(\w+)', query, re.IGNORECASE)
            table_names += re.findall(r'JOIN\s+(\w+)', query, re.IGNORECASE)
        return table_names
    except Exception as e:
        print(traceback.format_exc())
        raise RuntimeError("An error occurred while extracting table names from the SQL query")

def get_model_by_table_name(table_name, BaseModel):
    try:
        return BaseModel.get_class_by_tablename(table_name)
    except Exception as e:
        print(traceback.format_exc())
        raise RuntimeError("An error occurred while getting the model by table name")









