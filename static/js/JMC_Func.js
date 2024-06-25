// Display Flash Message
function displayFlashMessage(message, category) {
    const flashContainer = document.querySelector('.flash-messages');
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${category}`;
    alertDiv.textContent = message;
    flashContainer.appendChild(alertDiv);
}


//SQLite Browser Memory
let db;

// Check if the DB is in browser memory    
window.onload = async function() {
    const binaryArray = JSON.parse(localStorage.getItem('database'));
    if (binaryArray) {
        const SQL = await initSqlJs({ locateFile: filename => `/static/js/${filename}` });
        db = new SQL.Database(Uint8Array.from(binaryArray));
        await fetch('/set_use_in_memory_db', {method: 'POST'});
        if (window.location.pathname.endsWith('BrowserMemoryDB')) {
            displayFlashMessage('DB in browser memory', 'info');
        }
    } else {
        if (window.location.pathname.endsWith('BrowserMemoryDB')) {
            displayFlashMessage('No DB in browser memory', 'warning');
        }
    }
};

// Get SQL from server and create table in browser memory
async function CreateDB() {
    if (localStorage.getItem('database')) {
        if (!confirm('Existing DB in browser memory will be overwritten. Continue?')) {
            return;
        }
    }
    const response = await fetch('/get_create_table_sql');
    const data = await response.json();
    const SQL = await initSqlJs({ locateFile: filename => `/static/js/${filename}` });
    db = new SQL.Database();
    db.run(data.sql);
    const binaryArray = db.export();
    localStorage.setItem('database', JSON.stringify(Array.from(binaryArray)));
    update_page('/BrowserMemoryDB');
}

//Upload DB to Browser Memory
async function UploadDB() {
    if (localStorage.getItem('database')) {
        if (!confirm('Existing DB in browser memory will be overwritten. Continue?')) {
            return;
        }
    }
    const inputElement = document.createElement('input');
    inputElement.type = 'file';
    inputElement.accept = '.sqlite, .db';
    inputElement.addEventListener('change', function(event) {
        const file = event.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function(e) {
            const arrayBuffer = e.target.result;
            const data = new Uint8Array(arrayBuffer);
            const config = {locateFile: filename => `/static/js/${filename}`};
            initSqlJs(config).then(function(SQL) {
                const db = new SQL.Database(data);
                const binaryArray = db.export();
                localStorage.setItem('database', JSON.stringify(Array.from(binaryArray)));
                update_page('/BrowserMemoryDB'); // Call update_page or other necessary functions
            });
        };
        reader.readAsArrayBuffer(file);
    });
    inputElement.click();
}

//Download DB from Browser Memory and remove it
async function DownloadDB() {
    if (db) {
        const binaryArray = db.export();
        const blob = new Blob([binaryArray]);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'notes.db';
        a.click();
        localStorage.removeItem('database');
        db = null;
        await fetch('/unset_use_in_memory_db', {method: 'POST'});
        await fetch('/logout');
        update_page('/BrowserMemoryDB');
    }else{
        alert('No DB in browser memory');
    } 
}
      
//SocketIO communication
document.addEventListener('DOMContentLoaded', function () {
    const socket = io.connect();
    socket.on('connect', function() {
        var RoomId = socket.id;
        document.cookie = "room_id=" + RoomId + "; SameSite=None; Secure";
        console.log('Connected to server');
    });
    socket.on('json_data', async function(data) {
        console.log('JSON data received from server:', data);
        const sqlStatement = data.sql[0]
        console.log(sqlStatement);
        let result = [];
        if (sqlStatement.trim().toUpperCase().startsWith('SELECT')) {
            console.log('exec SQL statement:', sqlStatement);   
            result = db.exec(sqlStatement);    
            console.log(result);
        } else {
            console.log('run SQL statement:', sqlStatement);
            try {
                db.run(sqlStatement);
                console.log('Rows modified:', db.getRowsModified());
                const dbData = db.export();
                localStorage.setItem('database', JSON.stringify(Array.from(dbData)));         
            } catch (error) {
                console.error('Error executing SQL statement:', error);
            }
        }

        const ClientResponse = { message: result };
        fetch('/ClientResponse', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(ClientResponse)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            console.log('Data sent successfully to server');
        })
        .catch(error => console.error('Error:', error));
    });

    socket.on('disconnect', function() {
        console.log('Disconnected from server');
    });
});    

//Submit Form
function submitForm(formId, FetchRoute) {
    var formData = new FormData(document.getElementById(formId));
    fetch(FetchRoute, {
        method: 'POST',
        body: formData
    })
    .then(response => response.text())
    .then(data => {
        document.documentElement.innerHTML = data;
        initialize();
    })
    .catch(error => console.error('Error:', error));
}

// Get and update link content without reloading the page
initialize();
function initialize() {
    console.log('Initializing');
    document.querySelectorAll('.fetch-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            fetch(e.target.href)
                .then(response => response.text())
                .then(data => {
                    document.documentElement.innerHTML = data;
                    window.history.pushState({}, '', e.target.href);  
                    initialize();  
                    window.onload();
                })
                .catch(error => { console.error('Error:', error);});
        });
    });
}

// Update page content without reloading the page
function update_page(route){
    fetch(route)
    .then(response => response.text())
    .then(data => {
        document.documentElement.innerHTML = data;
        window.history.pushState({}, '', route);  
        initialize(); 
        window.onload();
    })
    .catch(error => { console.error('Error:', error);});
}