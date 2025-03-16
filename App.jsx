import React, { useState } from 'react'
import Input from './Input'
import List from './List'

export default function App() {
    let [todos, setTodos] = useState(['breakfast', 'lunch', 'dinner'])

    const addTodo = (value) => {
        setTodos([...todos, value]);
    }

    return (
        <div className='container mt-4'>
           <Input addTodo={addTodo} />
           <List todos={todos} />
        </div>
    )
}
